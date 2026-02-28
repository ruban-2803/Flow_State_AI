"""
analyzer.py - Computer Vision logic for Cuber's AI Coach
Uses Farneback Optical Flow to detect Recognition Pauses in Rubik's Cube solves.
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class Pause:
    start_time: float
    end_time: float
    duration: float

    @property
    def label(self) -> str:
        return f"{self.start_time:.2f}s – {self.end_time:.2f}s ({self.duration:.2f}s)"


@dataclass
class AnalysisResult:
    total_time: float
    fps: float
    frame_count: int
    timestamps: List[float]
    intensities: List[float]
    pauses: List[Pause]
    total_pause_time: float
    flow_score: float  # % of time in motion
    advice: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_time": round(self.total_time, 2),
            "fps": round(self.fps, 2),
            "frame_count": self.frame_count,
            "timestamps": [round(t, 3) for t in self.timestamps],
            "intensities": [round(i, 4) for i in self.intensities],
            "pauses": [
                {
                    "start_time": round(p.start_time, 3),
                    "end_time": round(p.end_time, 3),
                    "duration": round(p.duration, 3),
                }
                for p in self.pauses
            ],
            "total_pause_time": round(self.total_pause_time, 2),
            "flow_score": round(self.flow_score, 1),
            "advice": self.advice,
        }


def _compute_optical_flow_intensity(
    prev_gray: np.ndarray, curr_gray: np.ndarray
) -> float:
    """Compute mean magnitude of Farneback optical flow between two frames."""
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray,
        curr_gray,
        None,
        pyr_scale=0.5,
        levels=3,
        winsize=15,
        iterations=3,
        poly_n=5,
        poly_sigma=1.2,
        flags=0,
    )
    magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    return float(np.mean(magnitude))


def _detect_pauses(
    timestamps: List[float],
    intensities: List[float],
    threshold: float = 2.0,
    min_pause_duration: float = 0.5,
) -> List[Pause]:
    """
    Identify contiguous regions where intensity < threshold for >= min_pause_duration.
    """
    pauses: List[Pause] = []
    in_pause = False
    pause_start = 0.0

    for i, (t, intensity) in enumerate(zip(timestamps, intensities)):
        if intensity < threshold:
            if not in_pause:
                in_pause = True
                pause_start = t
        else:
            if in_pause:
                duration = t - pause_start
                if duration >= min_pause_duration:
                    pauses.append(
                        Pause(
                            start_time=pause_start,
                            end_time=t,
                            duration=duration,
                        )
                    )
                in_pause = False

    # Close any open pause at end of video
    if in_pause and timestamps:
        t = timestamps[-1]
        duration = t - pause_start
        if duration >= min_pause_duration:
            pauses.append(
                Pause(
                    start_time=pause_start,
                    end_time=t,
                    duration=duration,
                )
            )

    return pauses


def _generate_advice(
    total_time: float,
    pauses: List[Pause],
    total_pause_time: float,
    flow_score: float,
) -> List[str]:
    """Generate personalized coaching advice based on analysis metrics."""
    advice = []
    num_pauses = len(pauses)

    # Flow score advice
    if flow_score >= 85:
        advice.append(
            "🟢 Excellent lookahead! Your flow score is outstanding — you're spending most of your solve in continuous motion."
        )
    elif flow_score >= 70:
        advice.append(
            "🟡 Good flow overall. You're moving well, but there are a few spots where your lookahead breaks down. Focus on tracking the next pieces *while* executing your current algorithm."
        )
    else:
        advice.append(
            "🔴 Your flow score indicates significant pausing. Work on lookahead drills: practice each stage slowly while consciously scanning ahead for the next piece's location."
        )

    # Pause count advice
    if num_pauses == 0:
        advice.append(
            "🏆 Zero recognition pauses detected — you executed this solve with machine-like fluency!"
        )
    elif num_pauses <= 3:
        advice.append(
            f"✅ Only {num_pauses} pause(s) detected. Identify which stage these occur in (F2L, OLL, PLL?) and drill that specific transition."
        )
    elif num_pauses <= 7:
        advice.append(
            f"⚠️ {num_pauses} pauses detected. This is common at intermediate levels. Consider learning full OLL/PLL to reduce recognition time."
        )
    else:
        advice.append(
            f"🛑 {num_pauses} pauses detected — averaging one every {total_time/num_pauses:.1f}s. Focus on one stage at a time: drill F2L lookahead first, then OLL recognition, then PLL."
        )

    # Longest pause
    if pauses:
        longest = max(pauses, key=lambda p: p.duration)
        advice.append(
            f"⏱️ Your longest pause was {longest.duration:.2f}s at the {longest.start_time:.1f}s mark. Review that moment in the video to identify what caused the hesitation."
        )

    # Total pause time
    if total_pause_time > 5:
        advice.append(
            f"📉 You spent {total_pause_time:.1f}s completely paused. If you could halve that, your solve time would drop dramatically. Try 'slow solve' practice at 50% speed with no pauses allowed."
        )
    elif total_pause_time > 2:
        advice.append(
            f"📊 {total_pause_time:.1f}s of total pause time. You're close to elite-level flow — targeted lookahead drills for 10 minutes daily can close this gap fast."
        )

    return advice


def analyze_video(
    video_path: str,
    intensity_threshold: float = 2.0,
    min_pause_duration: float = 0.5,
    downsample_width: int = 320,
) -> AnalysisResult:
    """
    Main analysis pipeline. Opens video, computes per-frame optical flow intensity,
    detects pauses, and generates coaching advice.

    Args:
        video_path: Path to the uploaded video file.
        intensity_threshold: Mean optical flow magnitude below which we consider a frame "paused".
        min_pause_duration: Minimum contiguous pause length (seconds) to be reported.
        downsample_width: Resize frames to this width for speed (aspect ratio preserved).

    Returns:
        AnalysisResult dataclass with all metrics.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0  # Fallback
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_time = frame_count / fps

    logger.info(
        f"Video: {frame_count} frames @ {fps:.1f} fps = {total_time:.2f}s total"
    )

    timestamps: List[float] = []
    intensities: List[float] = []

    # Read first frame
    ret, frame = cap.read()
    if not ret:
        cap.release()
        raise ValueError("Could not read first frame from video.")

    # Compute target size (preserve aspect ratio)
    h, w = frame.shape[:2]
    scale = downsample_width / w
    target_size = (downsample_width, int(h * scale))

    def preprocess(f):
        resized = cv2.resize(f, target_size)
        return cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    prev_gray = preprocess(frame)
    frame_idx = 1

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        curr_gray = preprocess(frame)
        intensity = _compute_optical_flow_intensity(prev_gray, curr_gray)

        t = frame_idx / fps
        timestamps.append(t)
        intensities.append(intensity)

        prev_gray = curr_gray
        frame_idx += 1

    cap.release()

    # Smooth intensities (rolling mean over ~0.2s window) to reduce noise
    window = max(1, int(fps * 0.2))
    kernel = np.ones(window) / window
    smoothed = np.convolve(intensities, kernel, mode="same").tolist()

    pauses = _detect_pauses(
        timestamps, smoothed, threshold=intensity_threshold, min_pause_duration=min_pause_duration
    )

    total_pause_time = sum(p.duration for p in pauses)
    moving_time = total_time - total_pause_time
    flow_score = (moving_time / total_time * 100) if total_time > 0 else 0.0

    advice = _generate_advice(total_time, pauses, total_pause_time, flow_score)

    return AnalysisResult(
        total_time=total_time,
        fps=fps,
        frame_count=frame_idx,
        timestamps=timestamps,
        intensities=smoothed,
        pauses=pauses,
        total_pause_time=total_pause_time,
        flow_score=flow_score,
        advice=advice,
    )
