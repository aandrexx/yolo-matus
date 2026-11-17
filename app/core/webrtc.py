import asyncio

from aiortc import VideoStreamTrack
from av import VideoFrame

from app.core.gestor_camaras import GestorCamaras


class CamaraVideoTrack(VideoStreamTrack):
    def __init__(self, gestor: GestorCamaras, camara_id: int):
        super().__init__()
        self.gestor = gestor
        self.camara_id = camara_id

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame, _ = await asyncio.to_thread(self.gestor.frame_bgr, self.camara_id)
        while frame is None:
            await asyncio.sleep(0.05)
            frame, _ = await asyncio.to_thread(self.gestor.frame_bgr, self.camara_id)

        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame
