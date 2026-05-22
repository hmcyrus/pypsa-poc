We will use following algorithm to parse a geo map of a power transmission connectivities like [this](https://github.com/hmcyrus/pypsa-poc/blob/main/grids-substations-data-pgcb/network-geo-map.pdf)

- read the legends from the top right to understand what the map represents - lines and substations of different voltage levels, HVDC BtB station, and different power plants
- read the scale of the map from the bottom left corner to get an approximate length of each power line in KM.
- start from the north-west corner of the map located in the top left corner of the file - which is panchagarh for current file. then apply depth first search algo to explore different nodes in this graph of power transmission connectivity. while exploring the nodes of graph keep estimating the length of edge in parallel
- number of parallel lines connecting the same nodes represent the number of circuit in that line 
- provide the final output - start node(location), end node(location), voltage level(from the color of the line), approx length(based on the scale in KM), Line name (following the below mentioned naming convention)

### Line naming convention for the `Line name` column

`<bus0_name>_<bus1_name>_Line_<ckt_number>` -> bus0_name is the name of start node postfixed by the voltage level, bus1_name is the end node postfixed the same way 
ckt_number should correspond to the number of entries in the file for this line. for example, for double lines represented by two parallel lines should yield two rows in the file with the same bus0_name and bus1_name differing only in number, starting from 1
For example, `Panchagarh_132kVtoThakurgaon_132kV_Line1`, `Mirzapur_132kVtoKaliakoir_230kV_Line3`
