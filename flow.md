#                 RELIABILITY LAB
```
 ┌─────────────────────────────────────────────┐
 │                  SERVICES                   │
 │                                             │
 │   Client                                    │
 │     │                                       │
 │     ▼                                       │
 │  ┌─────────────┐       ┌─────────────┐      │
 │  │ Service A   │──────►│ Service B   │      │
 │  │             │       │             │      │
 │  │ API         │       │ processing  │      │
 │  │ workers     │       │ tiny store  │      │
 │  │ queue       │       │             │      │
 │  └─────────────┘       └─────────────┘      │
 │                                             │
 └─────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────┐
 │                SRE CONTROL                  │
 │                                             │
 │  dependency: normal / slow / error / timeout│
 │  traffic: normal / surge                    │
 │  retries: on / off                          │
 │  shedding: on / off                         │
 │                                             │
 └─────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────┐
 │                 MONITORING                  │
 │                                             │
 │                 Prometheus                  │
 │                                             │
 │  latency | errors | queue | workers         │
 │  dependency | retries | rejections | SLO    │
 │                                             │
 └─────────────────────────────────────────────┘
