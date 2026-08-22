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

