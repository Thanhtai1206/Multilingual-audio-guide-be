"""Test cho model AudioFile."""
import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.models.audio_file import AudioFile
from app.models.enums import Status


def tao_audio_hop_le(**ghi_de) -> AudioFile:
    du_lieu = {"translation_id": "652f1c2a9b1e8a0012345678", "voice": "ja-JP-NanamiNeural"}
    du_lieu.update(ghi_de)
    return AudioFile(**du_lieu)


def test_moi_tao_la_pending_chua_can_file():
    audio = tao_audio_hop_le()
    assert audio.status == Status.PENDING
    assert audio.format == "mp3"
    assert audio.file_path is None and audio.size_bytes is None


def test_audio_done_hop_le():
    audio = tao_audio_hop_le(status="done", file_path="storage/audio/a.mp3", size_bytes=1024, duration_sec=74)
    assert audio.status == Status.DONE


def test_done_thieu_file_path_bi_tu_choi():
    with pytest.raises(ValidationError):
        tao_audio_hop_le(status="done", size_bytes=1024)


@pytest.mark.parametrize("size", [None, 0])
def test_done_nhung_file_rong_bi_tu_choi(size):
    with pytest.raises(ValidationError):
        tao_audio_hop_le(status="done", file_path="storage/audio/a.mp3", size_bytes=size)


def test_failed_khong_can_file():
    assert tao_audio_hop_le(status="failed").status == Status.FAILED


@pytest.mark.parametrize(
    "truong, gia_tri",
    [
        ("translation_id", ""),
        ("voice", ""),
        ("format", "MP3"),            # phải chữ thường
        ("format", "mp3.exe"),
        ("duration_sec", -1),
        ("size_bytes", -5),
        ("status", "finished"),       # không có trong Status
    ],
)
def test_du_lieu_sai_bi_tu_choi(truong, gia_tri):
    with pytest.raises(ValidationError):
        tao_audio_hop_le(**{truong: gia_tri})


def test_doc_tu_mongo_objectid_duoc_ep_thanh_str():
    audio = AudioFile.model_validate(
        {"_id": ObjectId(), "translation_id": "652f1c2a9b1e8a0012345678", "voice": "vi-VN-HoaiMyNeural"}
    )
    assert isinstance(audio.id, str) and len(audio.id) == 24
