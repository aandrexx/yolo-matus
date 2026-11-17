import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.camaras import (
    cerrar_sesion_webrtc,
    crear_sesion_webrtc,
    video_archivo,
)
from app.schemas import OfertaWebRTC


class FakeDB:
    def __init__(self, camera):
        self.camera = camera

    def get(self, model, camera_id):
        return self.camera if self.camera.id == camera_id else None


class FakeGestor:
    def frame_bgr(self, camera_id):
        return np.zeros((120, 160, 3), dtype=np.uint8), 1


class FakeRequest:
    def __init__(self):
        self.app = SimpleNamespace(
            state=SimpleNamespace(webrtc_connections={})
        )


class VideoStreamTests(unittest.IsolatedAsyncioTestCase):
    def test_video_file_is_served_with_its_video_type_and_range_support(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clip.mp4"
            path.write_bytes(b"video-data")
            camera = SimpleNamespace(id=1, url=str(path))
            app = FastAPI()
            app.get("/video")(lambda: video_archivo(1, FakeDB(camera)))

            with TestClient(app) as client:
                ranged = client.get("/video", headers={"Range": "bytes=1-4"})

        self.assertEqual(ranged.status_code, 206)
        self.assertEqual(ranged.headers["content-type"], "video/mp4")
        self.assertEqual(ranged.content, b"ideo")

    async def test_webrtc_offer_receives_video_and_can_close_session(self):
        request = FakeRequest()
        camera = SimpleNamespace(id=1, url=r"D:\videos\clip.mp4", activa=True)
        db = FakeDB(camera)
        client = RTCPeerConnection()
        received_track = asyncio.get_running_loop().create_future()

        @client.on("track")
        def on_track(track):
            if not received_track.done():
                received_track.set_result(track)

        client.addTransceiver("video", direction="recvonly")
        offer = await client.createOffer()
        await client.setLocalDescription(offer)

        try:
            answer = await crear_sesion_webrtc(
                1,
                OfertaWebRTC(sdp=client.localDescription.sdp, type="offer"),
                request,
                db,
                FakeGestor(),
            )
            await client.setRemoteDescription(
                RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])
            )

            track = await asyncio.wait_for(received_track, timeout=8)
            frame = await asyncio.wait_for(track.recv(), timeout=8)
            self.assertEqual((frame.width, frame.height), (160, 120))
            await cerrar_sesion_webrtc(1, answer["session_id"], request, db)
            self.assertNotIn(answer["session_id"], request.app.state.webrtc_connections)
        finally:
            await client.close()
            for peer in list(request.app.state.webrtc_connections.values()):
                await peer.close()


if __name__ == "__main__":
    unittest.main()
