from moviepy.editor import ColorClip

def generate_sample_video(output_path="sample_video.mp4"):
    """Generate a simple red video clip for testing MoviePy."""
    clip = ColorClip(size=(320, 240), color=(255, 0, 0), duration=2)
    clip.write_videofile(output_path, fps=24)
    return output_path

if __name__ == "__main__":
    path = generate_sample_video()
    print(f"Sample video written to {path}")
