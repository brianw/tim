import unittest

from llmmetrics import METRIC_NAMES, parse_context_window, parse_metrics


METRICS_BODY = "\n".join(f"# TYPE {name} gauge\n{name} {index}" for index, name in enumerate(sorted(METRIC_NAMES)))


class ParseMetricsTest(unittest.TestCase):
    def test_parses_all_metrics(self):
        metrics = parse_metrics(METRICS_BODY)

        self.assertEqual(metrics.keys(), METRIC_NAMES)

    def test_rejects_missing_metric(self):
        with self.assertRaises(ValueError):
            parse_metrics("\n".join(METRICS_BODY.splitlines()[:-2]))

    def test_rejects_unknown_metric(self):
        with self.assertRaises(ValueError):
            parse_metrics(f"{METRICS_BODY}\nunknown_metric 1")

    def test_rejects_duplicate_metric(self):
        name = next(iter(METRIC_NAMES))

        with self.assertRaises(ValueError):
            parse_metrics(f"{METRICS_BODY}\n{name} 1")


class ParseContextWindowTest(unittest.TestCase):
    def test_parses_shared_context_window(self):
        context_window = parse_context_window([{"n_ctx": 4096}, {"n_ctx": 4096}])

        self.assertEqual(context_window, 4096)

    def test_rejects_different_context_windows(self):
        with self.assertRaises(ValueError):
            parse_context_window([{"n_ctx": 4096}, {"n_ctx": 8192}])

    def test_rejects_no_slots(self):
        with self.assertRaises(ValueError):
            parse_context_window([])


if __name__ == "__main__":
    unittest.main()
