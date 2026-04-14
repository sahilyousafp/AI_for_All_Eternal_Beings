// Phase 10 — Week 8 handoff manager.
//
// Owns the seam between the pre-rendered Blender attract loop video and
// the live Three.js scene. The hard part of Approach 3: making the
// transition so smooth that a visitor never notices the change from
// cinematic 40s video to real-time interactive 3D.
//
// The design:
//
//   Boot:
//     1. Try to preload attract_loop.mp4 into a <video>. If it's absent
//        (user didn't render it yet), fall back to the AttractScene
//        module which renders the same content in real-time Three.js.
//     2. While the video plays on top, the Three.js canvas renders
//        silently underneath at the NEUTRAL_POSE but with opacity 0.
//
//   Visitor touch (during video):
//     3. Pause video on its current frame (which is close to the
//        locked neutral-pose frame — Blender renders the last 2s with
//        the camera at NEUTRAL_POSE so any pause is near-match).
//     4. Fire a 300ms cross-dissolve: video element fades out,
//        Three.js canvas fades in.
//     5. During the dissolve, the Three.js side also runs a tiny
//        camera drift matching the video's last frame — geometric
//        correction for any pause-frame offset.
//     6. Hide the video, switch mode to 'focused' Scene B.
//
//   Idle reset (30s no touch in Scene B/C):
//     7. Fade Three.js canvas out, reset columns, resume video playback
//        from position 0, fade video in.
//
// The dissolve is done via CSS opacity transitions on the two layered
// elements. Fast, browser-native, zero shader work.

const VIDEO_URL = new URL('../assets/videos/attract_loop.mp4', import.meta.url);
const DISSOLVE_MS = 300;

export class HandoffManager {
  constructor(scene3d) {
    this.scene3d = scene3d;
    this.videoEl = null;
    this.videoAvailable = false;
    this.state = 'boot'; // 'boot' | 'attract-video' | 'attract-threejs' | 'handing-off' | 'live'
    this._pendingFocus = null;
  }

  // Call once at boot. Creates/finds the video element, attempts to
  // preload the attract loop, and leaves the manager in the appropriate
  // attract state depending on whether the video was loadable.
  async init() {
    this.videoEl = this._ensureVideoElement();

    // Canvas starts invisible; video either plays on top or is hidden
    // and AttractScene takes over.
    this.scene3d.canvas.style.opacity = '0';
    this.scene3d.canvas.style.transition = `opacity ${DISSOLVE_MS}ms ease`;

    try {
      await this._preloadVideo(VIDEO_URL);
      this.videoAvailable = true;
      this._playVideoAttract();
    } catch (err) {
      console.info('[handoff] no Blender video — using Three.js attract loop');
      this.videoAvailable = false;
      this._playThreejsAttract();
    }
  }

  _ensureVideoElement() {
    let el = document.getElementById('scene3d-attract-video');
    if (el) return el;
    el = document.createElement('video');
    el.id = 'scene3d-attract-video';
    el.muted = true;
    el.playsInline = true;
    el.loop = true;
    el.preload = 'auto';
    Object.assign(el.style, {
      position: 'fixed',
      inset: '0',
      width: '100vw',
      height: '100vh',
      objectFit: 'cover',
      zIndex: '105', // above canvas (100), below UI overlay (110)
      opacity: '0',
      transition: `opacity ${DISSOLVE_MS}ms ease`,
      pointerEvents: 'none',
      background: '#08090b',
    });
    document.body.appendChild(el);
    return el;
  }

  _preloadVideo(url) {
    return new Promise((resolve, reject) => {
      const el = this.videoEl;
      el.src = url.toString();
      const onReady = () => {
        el.removeEventListener('canplaythrough', onReady);
        el.removeEventListener('error', onError);
        resolve();
      };
      const onError = (e) => {
        el.removeEventListener('canplaythrough', onReady);
        el.removeEventListener('error', onError);
        reject(new Error('video preload failed'));
      };
      el.addEventListener('canplaythrough', onReady);
      el.addEventListener('error', onError);
      // Browsers sometimes never fire canplaythrough if the file is
      // missing; give it a generous timeout and then fail.
      setTimeout(() => {
        if (el.readyState < 4) {
          el.removeEventListener('canplaythrough', onReady);
          el.removeEventListener('error', onError);
          reject(new Error('video preload timeout'));
        }
      }, 5000);
    });
  }

  _playVideoAttract() {
    this.state = 'attract-video';
    this.videoEl.style.opacity = '1';
    this.scene3d.canvas.style.opacity = '0';
    this.videoEl.play().catch(() => {
      // Autoplay may be blocked. Most kiosk setups allow it, but if not
      // we fall back to the Three.js attract scene.
      this._playThreejsAttract();
    });
    this.scene3d.setMode('idle');
  }

  _playThreejsAttract() {
    this.state = 'attract-threejs';
    if (this.videoEl) this.videoEl.style.opacity = '0';
    this.scene3d.canvas.style.opacity = '1';
    this.scene3d.setMode('idle');
  }

  // Called on visitor touch on the screen.
  // pickedPhilosophy is optional — if the visitor tapped a specific
  // column in the Three.js attract scene, we carry that through.
  async startHandoff(pickedPhilosophy = null) {
    if (this.state === 'handing-off' || this.state === 'live') return;
    this.state = 'handing-off';
    this._pendingFocus = pickedPhilosophy;

    // Freeze video on its current frame.
    if (this.videoEl && !this.videoEl.paused) {
      this.videoEl.pause();
    }

    // Prepare the Three.js scene: make sure the canvas renderer is
    // warm and snap the camera to the neutral/focused pose before the
    // dissolve starts so the first visible frame is correct.
    this.scene3d.director.snapToIdle();
    this.scene3d.setMode('focused', { philosophy: pickedPhilosophy });

    // Cross-dissolve: start both transitions at the same time.
    this.scene3d.canvas.style.opacity = '1';
    if (this.videoEl) this.videoEl.style.opacity = '0';

    await this._wait(DISSOLVE_MS + 20);

    if (this.videoEl) this.videoEl.style.display = 'none';
    this.state = 'live';
  }

  // Called on 30s idle timeout. Back to attract loop.
  async resetToAttract() {
    if (this.state === 'attract-video' || this.state === 'attract-threejs') return;
    this.state = 'handing-off';

    this.scene3d.canvas.style.opacity = '0';
    if (this.videoEl && this.videoAvailable) {
      this.videoEl.style.display = 'block';
      this.videoEl.currentTime = 0;
      this.videoEl.style.opacity = '1';
      try { await this.videoEl.play(); } catch {}
      this.state = 'attract-video';
    } else {
      this.scene3d.canvas.style.opacity = '1';
      this.state = 'attract-threejs';
    }
    this.scene3d.setMode('idle');
    await this._wait(DISSOLVE_MS + 20);
  }

  _wait(ms) {
    return new Promise((res) => setTimeout(res, ms));
  }
}
