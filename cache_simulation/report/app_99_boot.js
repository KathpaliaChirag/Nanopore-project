/* ---------- boot ---------- */
(function boot() {
  themeDefaults();
  const steps = [initTheme, initNav, initTiles, renderData, renderIndex, initAssoc10, initFair, initProfiles, initR2000, initTime, initLaptop, initLong, initSize, initHwa, initFlat, initWl];
  steps.forEach(fn => {
    try { fn(); } catch (err) { console.error("report init failed:", fn.name, err); }
  });
})();
