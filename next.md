#And I would keep the implementation clean:
```
Finish the application metrics
Build Prometheus recording/query rules
Build Grafana dashboards
Define actual SLIs
Define SLOs
Calculate error budget
Create a small incident model for MTTD/MTTR/MTBF
Run the failure experiments
Use the resulting data to demonstrate the reliability story
Then interview
```

##
Availability SLI
    = successful requests / total requests

Error Rate
    = failed requests / total requests

Therefore:
Availability SLI + Error Rate = 100%
