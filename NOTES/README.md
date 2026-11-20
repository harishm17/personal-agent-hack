# NOTES

Cross-stream requests. One file per owner: `NOTES/<STREAM>.md` (e.g. NOTES/WEB.md, NOTES/INTEGRATOR.md).
Append only. Each entry: time, from, file:line, the exact change and why.

```
## 13:05 from SERVER
web/src/api.ts:42 reads event.kind; contract says event.type. Change `event.kind` -> `event.type`.
```

The owner checks the box when done: `- [x]`. `NOTES/crosscheck.md` collects HIGH findings from `./hk crosscheck`.
