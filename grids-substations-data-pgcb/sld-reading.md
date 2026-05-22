When extracting a text representing a node name which stands for a phyical location like Rampura or Aminbazar we have apply a certain node
understanding alogrithm/approach.

For example. a physical location like Rampura can have multiple buses of multiple voltage level. blue for 132kv bus, pink for 230kv bus, purple color for 400kv bus.
Following are some non-breakable condition for power transmission connectivities

- Each bus connects with some other bus of the same voltage level. That means, a bus of N kv must always connect with another bus of same kv,
- Buses of one voltage level can connect with another bus of different voltage level only through transformers.
- different icons are shown in this doc ------
- For now, there are two kinds of transformers(trafos) -> load transformer, voltage level transformer( these are the trafos facilitating connection between buses with two different voltage levels)
- lines overlap each other but that overlap doesn't matter, we need to find the starting of a line from a bus and trace it to the end in another bus. the color of the line represents the voltage level too. legends ----
