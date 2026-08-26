#
                    ┌─────────────────┐
                    │  Script Runners │
                    └────────┬────────┘
                             │
                       controlled load
                             │
                             ▼
                    ┌─────────────────┐
                    │   Receiver A    │
                    │                 │
                    │ Bulkhead        │
                    │ Queue           │
                    │ Retry           │
                    │ Circuit Breaker │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    Saver B      │
                    └─────────────────┘

                             │
                          metrics
                             ▼
                    ┌─────────────────┐
                    │   Prometheus    │
                    └────────┬────────┘
                             │
                 ┌───────────┴───────────┐
                 ▼                       ▼
          ┌─────────────┐         ┌─────────────┐
          │   Grafana   │         │ Alertmanager │
          └─────────────┘         └─────────────┘
                 │                       │
              observe                  alert
                 │                       │
                 └───────────┬───────────┘
                             ▼
                    Incident / Response
