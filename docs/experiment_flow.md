# SRE Reliability Lab — Experiment Flow

```text
                         EXPERIMENT GENERATORS
                    +-----------------------------+
                    |                             |
                    | send.py                     |
                    | load.py                     |
                    | t.sh                        |
                    | chaos.py                    |
                    |                             |
                    +-------------+---------------+
                                  |
                                  | controlled traffic
                                  | failure injection
                                  | concurrency
                                  v
                       +-----------------------+
                       |      RECEIVER A       |
                       |                       |
                       | HTTP API              |
                       | Bulkhead              |
                       | Queue                 |
                       | Worker Pool           |
                       | Retry                 |
                       | Circuit Breaker       |
                       | Metrics               |
                       +----------+------------+
                                  |
                                  | HTTP dependency call
                                  v
                       +-----------------------+
                       |        SAVER B        |
                       |                       |
                       | Validation            |
                       | Persistence           |
                       | Slow behavior         |
                       | Error behavior        |
                       | Timeout behavior      |
                       | Health / Readiness    |
                       +-----------------------+
                                  |
                    +-------------+-------------+
                    |                           |
                    |                           |
                 metrics                      logs
                    |                           |
                    v                           v
             +-------------+              +-------------+
             | Prometheus  |              |    Alloy    |
             +------+------+              +------+------+
                    |                            |
                    |                            |
                    |                            v
                    |                       +---------+
                    |                       |  Loki   |
                    |                       +----+----+
                    |                            |
                    +-------------+--------------+
                                  |
                                  v
                            +-----------+
                            |  Grafana  |
                            +-----------+
                                  |
                    +-------------+-------------+
                    |                           |
              visualization                investigation
                    |                           |
                    |                           |
                    v                           |
             +-------------+                    |
             |   Alerts    |                    |
             | Alert Rules |                    |
             +------+------+                    |
                    |                           |
                    v                           |
             +-------------+                    |
             | Alertmanager|                    |
             +------+------+                    |
                    |                           |
                    | webhook                   |
                    v                           |
             +-------------+                    |
             |   Notify    |                    |
             +------+------+                    |
                    |                           |
                    | notification event        |
                    v                           |
               container logs                   |
                    |                           |
                    v                           |
                  Alloy                         |
                    |                           |
                    v                           |
                  Loki -------------------------+
