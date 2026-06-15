# llmmetrics

A small in-memory dashboard for one `llama-server`.

Start `llama-server` with metrics enabled:

```bash
llama-server --metrics
```

Run the dashboard:

```bash
uv run main.py
```

Open <http://localhost:3000>.

The default llama-server endpoint is `http://lab.dogg.ie:8080`. Override it or
the dashboard port with:

```bash
uv run main.py --llama-url http://localhost:8080 --port 3000
```

The app polls `/metrics` and `/slots` every five seconds and keeps one hour of
samples in memory. Any collection or parsing error terminates the process.

Run the tests:

```bash
uv run python -m unittest
```
