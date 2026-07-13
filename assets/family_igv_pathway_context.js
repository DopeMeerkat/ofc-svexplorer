(function () {
  function normalizeGene(value) {
    if (!value) return "";
    if (Array.isArray(value)) value = value[0];
    return String(value).split(/[;,]/)[0].trim().toUpperCase();
  }

  function geneFromFeature(feature) {
    if (!feature) return "";
    return normalizeGene(
      feature.pathwayGene ||
      feature.gene ||
      feature.gene_id ||
      feature.geneId ||
      feature.genes ||
      feature.Gene ||
      feature.GENE
    );
  }

  function featureFromContext(track, context) {
    if (!context) return null;
    if (context.pathwayGene || context.gene || context.genes || context.feature) {
      return context.feature || context;
    }
    if (track && typeof track.clickedFeatures === "function") {
      var clicked = track.clickedFeatures(context) || [];
      for (var i = 0; i < clicked.length; i += 1) {
        if (geneFromFeature(clicked[i])) return clicked[i];
      }
      return clicked[0] || null;
    }
    return null;
  }

  function pathwayMenuItem(feature) {
    var gene = geneFromFeature(feature);
    if (!gene) return null;
    return {
      label: "Pathway",
      click: function () {
        window.location.href = "/pathway?gene=" + encodeURIComponent(gene);
      }
    };
  }

  function patchContextMenuMethod(proto, methodName) {
    if (!proto || typeof proto[methodName] !== "function" || proto[methodName].__ofcPathwayPatched) {
      return false;
    }

    var original = proto[methodName];
    proto[methodName] = function () {
      var items = original.apply(this, arguments) || [];
      var context = arguments[0] || arguments[1];
      var feature = featureFromContext(this, context);
      var item = pathwayMenuItem(feature);
      if (!item) return items;

      var alreadyPresent = items.some(function (existing) {
        return existing && existing.label === item.label;
      });
      if (!alreadyPresent) {
        items.push(item);
      }
      return items;
    };
    proto[methodName].__ofcPathwayPatched = true;
    return true;
  }

  function patchTrack(track) {
    if (!track || track.__ofcPathwayPatched) return false;

    var patched = false;
    if (Array.isArray(track.contextMenuItemList)) {
      var originalItems = track.contextMenuItemList.slice();
      track.contextMenuItemList = function (context) {
        var items = originalItems.slice();
        var feature = featureFromContext(track, context);
        var item = pathwayMenuItem(feature);
        if (item) items.push(item);
        return items;
      };
      patched = true;
    } else if (typeof track.contextMenuItemList === "function") {
      var originalList = track.contextMenuItemList.bind(track);
      track.contextMenuItemList = function (context) {
        var items = originalList(context) || [];
        var feature = featureFromContext(track, context);
        var item = pathwayMenuItem(feature);
        if (item && !items.some(function (existing) { return existing && existing.label === item.label; })) {
          items.push(item);
        }
        return items;
      };
      patched = true;
    }

    track.__ofcPathwayPatched = patched;
    return patched;
  }

  function patchExistingBrowsers() {
    var igv = window.igv;
    if (!igv) return false;

    var patched = false;
    ["FeatureTrack", "BAMTrack", "TrackBase"].forEach(function (name) {
      if (igv[name] && igv[name].prototype) {
        patched = patchContextMenuMethod(igv[name].prototype, "contextMenuItemList") || patched;
        patched = patchContextMenuMethod(igv[name].prototype, "contextMenuItems") || patched;
      }
    });

    var browserCandidates = [];
    if (igv.browser) browserCandidates.push(igv.browser);
    if (Array.isArray(igv.browsers)) browserCandidates = browserCandidates.concat(igv.browsers);
    if (window.igvBrowser) browserCandidates.push(window.igvBrowser);

    browserCandidates.forEach(function (browser) {
      if (browser && Array.isArray(browser.trackViews)) {
        browser.trackViews.forEach(function (trackView) {
          patched = patchTrack(trackView.track) || patched;
        });
      }
    });

    return patched;
  }

  var attempts = 0;
  var timer = window.setInterval(function () {
    attempts += 1;
    var patched = patchExistingBrowsers();
    if (patched || attempts > 120) {
      window.clearInterval(timer);
    }
  }, 500);
})();
