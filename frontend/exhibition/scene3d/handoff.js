// Handoff manager — Week 1 stub.
// Owns the seam between the pre-rendered Blender attract loop video and
// the live Three.js scene. Week 8 implements the real preload + freeze-
// frame + cross-dissolve sequence. For now it just exposes the API the
// rest of the scene3d layer will call into.

export class HandoffManager {
  constructor(scene3d) {
    this.scene3d = scene3d;
    this.videoEl = null;
    this.state = 'idle'; // 'idle' | 'playing-video' | 'handing-off' | 'live'
  }

  attachVideo(videoEl) {
    this.videoEl = videoEl;
  }

  // Called on visitor touch. Week 8: freeze the video on its last frame,
  // fade the canvas in over 300ms, enter Scene B at the neutral pose.
  startHandoff() {
    this.state = 'handing-off';
    this.scene3d.setMode('focused');
    // TODO Week 8: cross-dissolve
    this.state = 'live';
  }

  // Called on 30s idle timeout. Back to attract loop.
  resetToAttract() {
    this.state = 'playing-video';
    this.scene3d.setMode('idle');
  }
}
