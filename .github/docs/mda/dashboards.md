# Dashboards (spec §12)

## 12.1 Native ADO dashboards — start here
Achievable: Chart-for-query widgets grouped by a field (sum of `Custom.MDAActiveEffortHours` / `Custom.MDATokens` by developer, tier, sprint, stage), and filtered query tiles per pre-built slice. Use one dashboard per project as the approximation of "select a project".
Not achievable natively: a live dropdown/slicer driving several widgets, or an ad hoc date-range picker. Widget filters are fixed by whoever configures the dashboard.

Base query (`python .github/scripts/mda.py ado queries` prints these):

```
Select [System.Id], [System.Title] From WorkItems
Where [System.Tags] Contains 'MDA-EffortRecord'
  And [Custom.MDAProject] = '<project>'
  And [Custom.MDAPhase] <> 'qa-execution'   -- keep manual QA as its own tile
```

Suggested tiles: effort by developer, effort by tier, effort by sprint, tokens by developer, QA manual execution (separate), cycles per story.

## 12.2 Power BI — only when dynamic filtering is actually needed
Connect Power BI to ADO Analytics/OData (`…/_odata/v4.0-preview/WorkItems?$filter=contains(Tags,'MDA-EffortRecord')&$select=…Custom_MDA*`). This gives the project dropdown, user filter, date range and cross-filtering; the report can be embedded back into an ADO dashboard.
Needs: Power BI Pro (minimum) for the builder/sharer, Analytics enabled with the custom fields exposed, and the report/workspace shared with viewers (separate from ADO access).
**Status: not built** — deferred per the spec's recommendation; licensing approval is an open item.
