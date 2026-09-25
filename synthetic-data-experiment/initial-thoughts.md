We are creating a power systems analysis tool using pypsa. The eventual goal is to model the power systems network of Bangladesh that would help us in economic dispatch, long term and short term load forecasting.

We have the Lines, Buses, Transformers, Generators and Loads at different point.

We have the daily MAXIMUM LOAD SERVED BY DIFFERENT GRID SUB-STATIONS for a given time range and a particular day’s data is provided in the excel file. 

We need to generate following in a reasonable way hourly load served by grid substations.

These data should respect the max limits implied by data and a min limits implied by the daily national aggregate. Analyze the synthetic data generation approaches we can consider to do that.

## Real world examples of generating synthetic load data

The thesis describes how hourly customer meter data from **Kraftringen** can be aggregated to **infer hourly load for medium-voltage substations**, then **generalized using attributes** such as hour of day, month, heating means, number of customers, and r**esident-owner count**. It also states that the available data covered **11 residential substations over 11 months in 2018.** 

That thesis is especially useful because it naturally motivates the synthetic-data question: if a utility only has coarse daily information for some substations, but wants hourly curves for planning, forecasting, or simulation, then the task becomes conditional time-series synthesis under partial observability.

https://lup.lub.lu.se/luur/download?func=downloadFile&recordOId=9030028&fileOId=9030032