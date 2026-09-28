"""Minimal Azure DevOps REST client (work items, WIQL, wiki, Analytics). Standard library only.

Unverified against a live ADO organisation in this repo's test-suite (tests use a stub
transport); validate with `mda ado check` before relying on it.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from .core import load_config
from .identity import pat_from_env


class AdoError(Exception):
    def __init__(self, status, message):
        super().__init__(f"ADO {status}: {message}")
        self.status = status
        self.message = message


def _default_transport(method, url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise AdoError(0, f"network error: {e}")


class AdoClient:
    def __init__(self, cfg=None, project=None, pat=None, transport=None, timeout=None):
        self.cfg = cfg or load_config()
        self.org = self.cfg["ado"]["org_url"]
        self.project = self.cfg["ado"]["project"] or project
        self.api = self.cfg["ado"]["api_version"]
        self.pat = pat or pat_from_env()
        self.transport = transport or _default_transport
        self.timeout = timeout or self.cfg["sync"]["http_timeout_seconds"]

    @property
    def configured(self) -> bool:
        return bool(self.org and self.pat and self.project)

    def _headers(self, content_type="application/json"):
        tok = base64.b64encode(f":{self.pat}".encode()).decode()
        return {"Authorization": f"Basic {tok}", "Content-Type": content_type,
                "Accept": "application/json"}

    def request(self, method, url, body=None, content_type="application/json", extra=None):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        headers = self._headers(content_type)
        headers.update(extra or {})
        status, hdrs, raw = self.transport(method, url, headers, data, self.timeout)
        text = raw.decode("utf-8", "replace") if raw else ""
        if status >= 400 or status == 0:
            raise AdoError(status, text[:400])
        try:
            return (json.loads(text) if text else {}), hdrs
        except ValueError:
            return {"_raw": text}, hdrs

    def _p(self, path, **q):
        q.setdefault("api-version", self.api)
        return f"{self.org}/{urllib.parse.quote(self.project)}/_apis/{path}?" + urllib.parse.urlencode(q, safe="$")

    # ---------------------------------------------------------------- probes
    def probe_scopes(self) -> dict:
        def ok(fn):
            try:
                fn()
                return True
            except AdoError as e:
                return False if e.status in (401, 403) else None  # None = inconclusive (e.g. network)
        wq = {"query": "Select [System.Id] From WorkItems Where [System.Id] = 0"}
        res = {
            "auth": ok(lambda: self.request("GET", f"{self.org}/_apis/connectionData?api-version=7.1-preview")),
            "work_items_read": ok(lambda: self.request("POST", self._p("wit/wiql"), wq)),
            "wiki_read": ok(lambda: self.request("GET", self._p("wiki/wikis"))),
            "analytics_read": ok(lambda: self.request(
                "GET", f"{self.org}/{urllib.parse.quote(self.project)}/_odata/v4.0-preview/WorkItems?$top=1&$select=WorkItemId")),
            # validateOnly performs the permission check without creating anything
            "work_items_write": ok(lambda: self.request(
                "POST", self._p("wit/workitems/$" + urllib.parse.quote(self.cfg["ado"]["effort_record_type"]),
                                validateOnly="true"),
                [{"op": "add", "path": "/fields/System.Title", "value": "mda-scope-probe"}],
                content_type="application/json-patch+json")),
        }
        res["wiki_write"] = None  # cannot be probed without writing; verified on first wiki append
        return res

    def analytics_fields_exposed(self) -> dict:
        names = [f.replace(".", "_") for f in self.cfg["ado"]["fields"].values()
                 if f != self.cfg["ado"]["fields"]["payload"]]
        out = {}
        for n in names:
            url = (f"{self.org}/{urllib.parse.quote(self.project)}/_odata/v4.0-preview/WorkItems"
                   f"?$top=1&$select=WorkItemId,{n}")
            try:
                self.request("GET", url)
                out[n] = True
            except AdoError as e:
                out[n] = False if e.status == 400 else None
        return out

    # ---------------------------------------------------------------- records
    def wiql(self, query: str) -> list:
        res, _ = self.request("POST", self._p("wit/wiql"), {"query": query})
        return [w["id"] for w in res.get("workItems", [])]

    def get_item(self, wid: int) -> dict:
        res, _ = self.request("GET", self._p(f"wit/workitems/{wid}", **{"$expand": "all"}))
        return res

    def find_record(self, key: str):
        f = self.cfg["ado"]["fields"]["key"]
        tag = self.cfg["ado"]["record_tag"]
        safe = key.replace("'", "''")
        q = (f"Select [System.Id] From WorkItems Where [System.Tags] Contains '{tag}' "
             f"And [System.Title] = '{safe}'")
        ids = self.wiql(q)
        return ids[0] if ids else None

    def upsert_record(self, key: str, fields: dict, payload: str, story_ref=None, wid=None):
        """Create or update one Effort Record. Title = key (stable, queryable). Falls back to a
        payload-only record if the custom fields are not defined in the process."""
        structured = self.cfg["ado"]["structured_fields"]
        for attempt in (structured, False):
            ops = [{"op": "add", "path": "/fields/System.Title", "value": key},
                   {"op": "add", "path": "/fields/System.Tags", "value": self.cfg["ado"]["record_tag"]}]
            if attempt:
                for k, v in fields.items():
                    ref = self.cfg["ado"]["fields"].get(k)
                    if ref and v is not None:
                        ops.append({"op": "add", "path": f"/fields/{ref}", "value": v})
                ops.append({"op": "add", "path": f"/fields/{self.cfg['ado']['fields']['payload']}", "value": payload})
            else:
                ops.append({"op": "add", "path": "/fields/System.Description",
                            "value": "<pre>" + payload.replace("&", "&amp;").replace("<", "&lt;") + "</pre>"})
            try:
                wid = wid or self.find_record(key)
                if wid:
                    self.request("PATCH", self._p(f"wit/workitems/{wid}"), ops,
                                 content_type="application/json-patch+json")
                    return {"id": wid, "created": False, "structured": attempt}
                if story_ref:
                    ops.append({"op": "add", "path": "/relations/-", "value": {
                        "rel": "System.LinkTypes.Hierarchy-Reverse",
                        "url": f"{self.org}/_apis/wit/workItems/{story_ref}"}})
                res, _ = self.request("POST", self._p("wit/workitems/$" + urllib.parse.quote(
                    self.cfg["ado"]["effort_record_type"])), ops, content_type="application/json-patch+json")
                return {"id": res.get("id"), "created": True, "structured": attempt}
            except AdoError as e:
                if attempt and e.status == 400 and ("TF51535" in e.message or "does not exist" in e.message
                                                    or "field" in e.message.lower()):
                    continue  # custom fields not present yet -> retry payload-only
                raise
        raise AdoError(400, "could not write record")

    def read_payload(self, key: str):
        wid = self.find_record(key)
        if not wid:
            return None
        item = self.get_item(wid)
        f = item.get("fields", {})
        raw = f.get(self.cfg["ado"]["fields"]["payload"])
        if raw is None:
            desc = f.get("System.Description", "")
            raw = desc.replace("<pre>", "").replace("</pre>", "").replace("&lt;", "<").replace("&amp;", "&")
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    def story_summary(self, story_id) -> dict:
        item = self.get_item(int(story_id))
        f = item.get("fields", {})
        return {"id": item.get("id"), "title": f.get("System.Title"), "type": f.get("System.WorkItemType"),
                "state": f.get("System.State"), "description": f.get("System.Description"),
                "acceptance_criteria": f.get("Microsoft.VSTS.Common.AcceptanceCriteria"),
                "tags": f.get("System.Tags"), "area": f.get("System.AreaPath"),
                "iteration": f.get("System.IterationPath")}

    # ---------------------------------------------------------------- wiki
    def wiki_append(self, page_path: str, markdown: str, wiki_id=None) -> dict:
        """Append (never replace) so history accumulates (spec s13)."""
        wiki = wiki_id or self.cfg["ado"]["wiki_id"]
        if not wiki:
            wikis, _ = self.request("GET", self._p("wiki/wikis"))
            if not wikis.get("value"):
                raise AdoError(404, "no wiki found in project")
            wiki = wikis["value"][0]["id"]
        url = self._p(f"wiki/wikis/{wiki}/pages", path=page_path)
        try:
            cur, hdrs = self.request("GET", url + "&includeContent=true")
            etag = hdrs.get("ETag") or hdrs.get("Etag")
            content = (cur.get("content") or "") + "\n\n---\n\n" + markdown
            extra = {"If-Match": etag} if etag else {}
        except AdoError as e:
            if e.status != 404:
                raise
            content, extra = markdown, {}
        res, _ = self.request("PUT", url, {"content": content}, extra=extra)
        return {"path": page_path, "id": res.get("id")}
