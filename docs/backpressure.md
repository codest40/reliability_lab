# BackPressure practices/forms

## Load shedding
```
B gets slow
    ↓
workers remain occupied
    ↓
capacity decreases
    ↓
queue grows
    ↓
queue fills
    ↓
new work is rejected
```

### Queueing
```
B gets slow
    ↓
workers remain occupied
    ↓
capacity decreases
    ↓
queue grows
    ↓
queue fills
    ↓
new work is NOT rejected, it has to wait until queue has space
```

