mergeInto(LibraryManager.library, {
  VfxWebDispatch: function (jsonPtr) {
    var payload = UTF8ToString(jsonPtr);
    if (window.vfxWebPlayer && typeof window.vfxWebPlayer.onUnityEvent === "function") {
      window.vfxWebPlayer.onUnityEvent(payload);
    }
  },
});
