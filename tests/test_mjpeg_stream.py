import unittest
from types import SimpleNamespace

from app.api.camaras import stream


class FakeRequest:
    def __init__(self):
        self.checks = 0

    async def is_disconnected(self):
        self.checks += 1
        return self.checks > 1


class FakeDB:
    def get(self, model, camara_id):
        return SimpleNamespace(id=camara_id)


class FakeGestor:
    def fotograma(self, camara_id):
        return b"jpeg-frame", 1


class MjpegStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_yields_a_new_jpeg_frame(self):
        response = await stream(1, FakeRequest(), FakeDB(), FakeGestor())

        self.assertIn("multipart/x-mixed-replace", response.media_type)
        frame = await anext(response.body_iterator)

        self.assertIn(b"--frame\r\n", frame)
        self.assertIn(b"Content-Type: image/jpeg\r\n", frame)
        self.assertTrue(frame.endswith(b"jpeg-frame\r\n"))
        await response.body_iterator.aclose()


if __name__ == "__main__":
    unittest.main()
