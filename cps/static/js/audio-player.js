// Calibre-Web Automated – SPDX-License-Identifier: GPL-3.0-or-later
// Audiobook player: native <audio>, resume position, skip, speed, sleep timer, lock-screen controls.
(function () {
  "use strict";
  var box = document.getElementById("player");
  var audio = document.getElementById("audio");
  if (!box || !audio) return;

  var seek = document.getElementById("seek");
  var play = document.getElementById("play");
  var cur = document.getElementById("time-current");
  var left = document.getElementById("time-left");
  var speed = document.getElementById("speed");
  var sleep = document.getElementById("sleep");
  var errorBox = document.getElementById("player-error");
  var saveRemote = box.getAttribute("data-save") === "true";
  var localKey = "cwa.audio.position." + box.getAttribute("data-key");
  var seeking = false;
  var lastSaved = 0;
  var sleepTimer = null;

  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage blocked */ } }
  function fmt(t) {
    t = Math.max(0, Math.floor(t || 0));
    var h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
    return (h ? h + ":" + String(m).padStart(2, "0") : m) + ":" + String(s).padStart(2, "0");
  }
  function render() {
    var d = audio.duration || 0;
    cur.textContent = fmt(audio.currentTime);
    left.textContent = "−" + fmt(d - audio.currentTime);
    if (!seeking && d) seek.value = String(Math.round(audio.currentTime / d * 1000));
    seek.style.setProperty("--fill", (d ? audio.currentTime / d * 100 : 0) + "%");
  }
  function save(force) {
    var now = Date.now();
    if (!force && now - lastSaved < 15000) return;
    lastSaved = now;
    var pos = audio.currentTime.toFixed(1);
    set(localKey, pos);
    if (!saveRemote) return;
    var body = new URLSearchParams();
    body.set("bookmark", pos);
    fetch(box.getAttribute("data-bookmark-url"), {
      method: "POST", credentials: "same-origin", keepalive: true,
      headers: { "X-CSRFToken": document.querySelector("meta[name='csrf-token']").content },
      body: body
    }).catch(function () { /* the local copy still has it */ });
  }
  function setPlaying(on) {
    box.classList.toggle("is-playing", on);
    play.setAttribute("aria-label", play.getAttribute(on ? "data-label-pause" : "data-label-play"));
    if ("mediaSession" in navigator) navigator.mediaSession.playbackState = on ? "playing" : "paused";
  }
  function skip(seconds) {
    audio.currentTime = Math.min(Math.max(0, audio.currentTime + seconds), audio.duration || Infinity);
    save(true);
  }

  // Resume: the later of the server bookmark and this browser's copy.
  var remote = parseFloat(box.getAttribute("data-bookmark"));
  var local = parseFloat(get(localKey));
  var resumeAt = Math.max(isNaN(remote) ? 0 : remote, isNaN(local) ? 0 : local);
  var savedRate = parseFloat(get("cwa.audio.rate"));
  if (!isNaN(savedRate)) speed.value = String(savedRate);

  audio.addEventListener("loadedmetadata", function () {
    if (resumeAt > 0 && resumeAt < audio.duration - 5) audio.currentTime = resumeAt;
    audio.playbackRate = parseFloat(speed.value) || 1;
    seek.disabled = false;
    play.disabled = false;
    render();
  });
  audio.addEventListener("timeupdate", function () { render(); save(false); });
  audio.addEventListener("play", function () { setPlaying(true); });
  audio.addEventListener("pause", function () { setPlaying(false); save(true); });
  audio.addEventListener("ended", function () { setPlaying(false); save(true); });
  audio.addEventListener("error", function () { errorBox.hidden = false; play.disabled = true; });
  audio.src = box.getAttribute("data-src");

  play.addEventListener("click", function () {
    if (audio.paused) audio.play().catch(function () { errorBox.hidden = false; });
    else audio.pause();
  });
  Array.prototype.forEach.call(box.querySelectorAll("[data-skip]"), function (b) {
    b.addEventListener("click", function () { skip(parseInt(b.getAttribute("data-skip"), 10)); });
  });
  seek.addEventListener("input", function () {
    seeking = true;
    var d = audio.duration || 0;
    cur.textContent = fmt(seek.value / 1000 * d);
    seek.style.setProperty("--fill", seek.value / 10 + "%");
  });
  seek.addEventListener("change", function () {
    seeking = false;
    if (audio.duration) audio.currentTime = seek.value / 1000 * audio.duration;
    save(true);
  });
  speed.addEventListener("change", function () {
    audio.playbackRate = parseFloat(speed.value) || 1;
    set("cwa.audio.rate", speed.value);
  });
  sleep.addEventListener("change", function () {
    clearTimeout(sleepTimer);
    var minutes = parseInt(sleep.value, 10);
    if (minutes > 0) {
      sleepTimer = setTimeout(function () { audio.pause(); sleep.value = "0"; }, minutes * 60000);
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.target.closest("input, select, textarea")) return;
    if (e.key === " " || e.key === "k") { e.preventDefault(); play.click(); }
    else if (e.key === "ArrowLeft" || e.key === "j") skip(-30);
    else if (e.key === "ArrowRight" || e.key === "l") skip(30);
  });
  document.addEventListener("visibilitychange", function () { if (document.hidden) save(true); });
  window.addEventListener("pagehide", function () { save(true); });

  if ("mediaSession" in navigator) {
    var title = document.querySelector(".player-title").textContent;
    var artist = document.querySelector(".player-author").textContent;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: title, artist: artist,
      artwork: [{ src: box.getAttribute("data-artwork") }]
    });
    navigator.mediaSession.setActionHandler("play", function () { audio.play(); });
    navigator.mediaSession.setActionHandler("pause", function () { audio.pause(); });
    navigator.mediaSession.setActionHandler("seekbackward", function () { skip(-30); });
    navigator.mediaSession.setActionHandler("seekforward", function () { skip(30); });
    try {
      navigator.mediaSession.setActionHandler("seekto", function (d) { audio.currentTime = d.seekTime; save(true); });
    } catch (e) { /* older browsers */ }
  }
})();
