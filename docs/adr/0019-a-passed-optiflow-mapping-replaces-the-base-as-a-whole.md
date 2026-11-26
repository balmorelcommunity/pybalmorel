# A passed OptiFlow Mapping replaces the base as a whole

pybalmorel ships a base OptiFlow Mapping, made for the newest OptiFlow
design (Fristed, 2027). `to_iamc` uses it when the caller passes no Mapping.
When the caller passes one, it replaces the base Mapping as a whole: none of
the base rows apply. Only the rows for flows that the add-on itself names
(what OptiFlow gives Balmorel through `HeatBuffer` and `ElecBuffer`) apply
whichever Mapping is used.

OptiFlow designs differ between studies, and a study's Mapping is written
for its own design. Process names recur across designs but can mean
different things in each: a base row that matches a flow in another design
may report it under the wrong variable, or report something the study's
Mapping already reports under another pattern. Rows match by regular
expressions, so pybalmorel can't tell whether a passed row and a base row
cover the same flows. Any rule for merging the two would therefore count
some flows twice or drop some, without telling anyone.

## Considered options

- **Passed rows added to the base rows.** Every study would get the base
  reporting for free. A study whose design differs would also get base rows
  that match its flows by accident. Its own rows for the same flows would
  then count them twice.
- **Passed rows override the base rows they share a pattern with.** This
  only works when both write the pattern in the same way. A passed
  `MDO_Eff|LNG_Eff` and a base `MDO_Eff` would both apply.

## Consequences

- To change a few rows of the base design, copy `optiflow_base.csv`, edit
  the copy and pass it.
- A study's own Mapping gets nothing that is added to the base Mapping
  later, such as new Primary Energy or Secondary Energy rows. Its author
  has to copy those rows in.
- With the base Mapping, a Conversion Note lists the base rows that match
  no flow. Many unmatched rows mean the study has another design and needs
  its own Mapping.
