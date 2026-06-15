import argparse
import asyncio
import time
from collections import deque
from pathlib import Path

from aiohttp import ClientSession, web


METRIC_NAMES = {
    "llamacpp:prompt_tokens_total",
    "llamacpp:prompt_seconds_total",
    "llamacpp:tokens_predicted_total",
    "llamacpp:tokens_predicted_seconds_total",
    "llamacpp:n_decode_total",
    "llamacpp:n_tokens_max",
    "llamacpp:n_busy_slots_per_decode",
    "llamacpp:prompt_tokens_seconds",
    "llamacpp:predicted_tokens_seconds",
    "llamacpp:requests_processing",
    "llamacpp:requests_deferred",
}
INDEX_HTML = Path(__file__).with_name("static").joinpath("index.html")


def parse_metrics(body):
    metrics = {}
    for line in body.splitlines():
        if not line or line.startswith("#"):
            continue
        name, value = line.split()
        if name not in METRIC_NAMES or name in metrics:
            raise ValueError(f"unexpected metric: {name}")
        metrics[name] = float(value)
    if metrics.keys() != METRIC_NAMES:
        raise ValueError(f"missing metrics: {METRIC_NAMES - metrics.keys()}")
    return metrics


def parse_context_window(slots):
    context_windows = {slot["n_ctx"] for slot in slots}
    if len(context_windows) != 1:
        raise ValueError(f"unexpected context windows: {context_windows}")
    return context_windows.pop()


async def fetch_sample(session, llama_url):
    async with session.get(f"{llama_url}/metrics") as response:
        response.raise_for_status()
        metrics = parse_metrics(await response.text())
    async with session.get(f"{llama_url}/slots") as response:
        response.raise_for_status()
        context_window = parse_context_window(await response.json())
    return {
        "timestamp": time.time() * 1000,
        "context_window": context_window,
        "metrics": metrics,
    }


async def collect_samples(samples, llama_url, interval):
    async with ClientSession() as session:
        while True:
            await asyncio.sleep(interval)
            samples.append(await fetch_sample(session, llama_url))


async def index(request):
    return web.FileResponse(INDEX_HTML)


async def get_samples(request):
    return web.json_response(list(request.app["samples"]))


def create_app(samples):
    app = web.Application()
    app["samples"] = samples
    app.add_routes([web.get("/", index), web.get("/samples", get_samples)])
    return app


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llama-url", default="http://lab.dogg.ie:8080")
    parser.add_argument("--port", type=int, default=3000)
    return parser.parse_args()


async def run(llama_url, port):
    samples = deque(maxlen=720)
    async with ClientSession() as session:
        samples.append(await fetch_sample(session, llama_url))
    app = create_app(samples)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, port=port).start()
    try:
        await collect_samples(samples, llama_url, 5)
    finally:
        await runner.cleanup()


def main():
    args = parse_args()
    asyncio.run(run(args.llama_url.rstrip("/"), args.port))


if __name__ == "__main__":
    main()
