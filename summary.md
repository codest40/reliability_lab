# What i have learned so far in practise

```
1. Dependency latency
       ↓
2. Worker concurrency
       ↓
3. Queueing
       ↓
4. Load shedding (backpressuere)

dependency latency
       ↓
timeout
       ↓
retry
       ↓
retry amplification
       ↓
queue buildup
       ↓
backpressure
       ↓
load shedding
       ↓
dependency health detection
       ↓
circuit opens
       ↓
recovery probe
       ↓
circuit closes
```

```
HTTP
├── requests
├── duration
├── errors
├── responses
└── in progress

DEPENDENCY
├── requests
├── duration
├── errors
├── timeouts
└── connection errors

WORKERS
├── total
├── busy
└── available

QUEUES
├── size
├── capacity
├── utilization
├── rejections
└── wait duration

RETRIES
├── retries
├── attempts
├── exhausted
└── delay

CIRCUIT BREAKER
├── state
├── transitions
├── rejections
├── opens
├── probes
├── probe success
└── probe failure

PROBES
├── total
├── success
├── failure
└── duration

BULKHEAD
├── capacity
├── active requests
└── rejections

DEPENDENCY HEALTH
├── health
└── under pressure

APPLICATION
├── processed
├── saved
└── invalid
