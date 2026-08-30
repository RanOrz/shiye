import threading
import unittest

from server.job_manager import JobManager


class JobManagerTests(unittest.TestCase):
    def test_job_moves_to_done_and_keeps_progress(self):
        finished = threading.Event()

        def processor(payload, progress):
            progress("transcribing", "正在转写")
            finished.set()
            return {"path": "/tmp/note.md", "value": payload["value"]}

        manager = JobManager(processor)
        job_id = manager.submit({"value": 7})
        self.assertTrue(finished.wait(1))
        job = manager.wait(job_id, timeout=1)

        self.assertEqual(job["status"], "done")
        self.assertEqual(job["result"]["value"], 7)
        self.assertEqual(job["stage"], "done")

    def test_job_failure_is_serialized(self):
        def processor(_payload, _progress):
            raise ValueError("bad media")

        manager = JobManager(processor)
        job_id = manager.submit({})
        job = manager.wait(job_id, timeout=1)

        self.assertEqual(job["status"], "error")
        self.assertIn("bad media", job["error"])
        self.assertEqual(job["error_code"], "MEDIA_UNKNOWN")
        self.assertEqual(job["error_stage"], "starting")

    def test_unknown_job_returns_none(self):
        manager = JobManager(lambda payload, progress: payload)
        self.assertIsNone(manager.get("missing"))


if __name__ == "__main__":
    unittest.main()
