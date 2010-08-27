// Object to hold various formatting functions that operate 
// on an .ocr_page div, containing .ocr_line spans.

function OcrLineFormatter() {
    //
    // Layout: Functions for arranging the lines in certain ways
    // TODO: Remove code dup between this and the ocr_page.js
    // file.
    //

    // parse bbox="0 20 500 300" into [0, 20, 500, 300]
    var parseBoundingBoxAttr = function(bbox) {
        var dims = [-1, -1, -1, -1];
        if (bbox.match(boxpattern)) {
            dims[0] = parseInt(RegExp.$1);
            dims[1] = parseInt(RegExp.$2); 
            dims[2] = parseInt(RegExp.$3);
            dims[3] = parseInt(RegExp.$4);            
        }
        return dims;
    }

    // Fudgy function to insert line breaks (<br />) in places
    // where there are large gaps between lines.  Significantly
    // improves the look of a block of OCR'd text.
    this.blockLayout = function(pagediv) {
        // insert space between each line
        resetState(pagediv);
        $("<span></span>").text("\u00a0").insertBefore(
            pagediv.find(".ocr_line").first().nextAll());        
        pagediv.removeClass("literal");
        pagediv.css("height", null);
        insertBreaks(pagediv);
    }


    this.lineLayout = function(pagediv) {
        resetState(pagediv);
        insertBreaks(pagediv);
        $(".ocr_line", pagediv).css("display", "block");
    }

    // Horrid function to try and position lines how they would be on
    // the source material.  TODO: Make this not suck.
    this.columnLayout = function(pagediv) {
        resetState(pagediv);
        var dims  = pagediv.data("bbox");
        var scale = (pagediv.outerWidth(true)) / dims[2];
        var offx = pagediv.offset().left;
        var offy = pagediv.offset().top;
        pagediv.height(((dims[3] - dims[1]) * scale) + 20);

        var heights = [];
        var orderedheights = [];
        var orderedwidths = [];        

        pagediv.addClass("literal");
        pagediv.children(".ocr_line").each(function(position, item) {
            $(item).children("br").remove();
            var lspan = $(item);
            var linedims = lspan.data("bbox");
            var x = ((linedims[0] - dims[0]) * scale) + offx;
            var y = ((linedims[1] - dims[1]) * scale) + offy; 
            var w = (linedims[2] * scale);
            var h = (linedims[3] * scale);
            lspan.css("top",    y).css("left",   x)
                .css("position", "absolute");
            heights.push(h);
            orderedheights.push(h);
            orderedwidths.push(w);
        });



        var stats = new Stats(heights);
        var medianfs = null;
        pagediv.children(".ocr_line").each(function(position, item) {
            //var lspan = $(item);
            //var iheight = lspan.height();
            //var iwidth = lspan.width();
            
            // if 'h' is within .25% of median, use the median instead    
            var h = orderedheights[position];
            var w = orderedwidths[position];
            var ismedian = false;
            if ((h / stats.median - 1) < 0.25) {
                h = stats.median;
                ismedian = true;
            } 

            // also clamp 'h' is min 3
            h = Math.max(h, 3);
            if (medianfs != null && ismedian) {
                $(item).css("font-size", medianfs);
            } else {            
                var fs = resizeToTarget($(item), h, w);
                if (medianfs == null && ismedian) {
                    medianfs = fs;
                }
            }
        });       
    }

    var resetState = function(pagediv) {
        $("span", pagediv).map(function(i, elem) {
            if ($.trim($(elem).text()) == "" || $.trim($(elem).text()) == "\u00a0") 
                return $(elem);
        }).remove();
        pagediv.find("br").remove();
        pagediv.removeClass("literal");
        pagediv.css("height", null);
        $(".ocr_line", pagediv).css("display", null);


    }


    var insertBreaks = function(pagediv) {
        var lastyh = -1;
        var lasth = -1;
        var lastitem;
        $(".ocr_line", pagediv).each(function(lnum, item) {
            var dims = $(item).data("bbox");
            var y = dims[1];  // bbox x, y, w, h
            var h = dims[3];
            if (dims[0] != -1) {
                $(item).attr("style", "");
                $(item).children("br").remove();
                if ((lastyh != -1 && lasth != -1) 
                        && (y - (h * 0.75) > lastyh || lasth < (h * 0.75))) {
                    $(lastitem).after($("<br />")).after($("<br />"));
                }
                lastitem = item;                
                lastyh = y + h;
                lasth = h;
            }                        
        });
    }

    var resizeToTarget = function(span, targetheight, targetwidth) {
        var iheight = span.height();
        var iwidth = span.width();
        var count = 0
        if (iheight < targetheight && iheight) {
            //alert("grow! ih: " + iheight + " th: " + targetheight);
            while (iheight < targetheight && iwidth < targetwidth) {
                var cfs = parseInt(span.css("font-size").replace("px", ""));
                span = span.css("font-size", (cfs + 1) + "px");
                iheight = span.height();
                count++;
                if (count > 50) {
                    //alert("growing too long: iheight: " + iheight + " th: " + targetheight);
                    break;
                }
            }
        } else if (iheight > targetheight) {
            while (iheight && iheight > targetheight) {
                var cfs = parseInt(span.css("font-size").replace("px", ""));
                span = span.css("font-size", (cfs - 1) + "px");
                iheight = span.height();
                //alert("ih: " + iheight + " fs:" + cfs + " th: " + targetheight);
                //alert("iheight: " + iheight + " fs: " + span.css("font-size") + " cfs: " + (cfs - 1));
                count++;
                if (count > 50) {
                    //alert("shrinking too long: iheight: " + iheight + " th: " + targetheight);
                    break;
                }
            }
        }
        return span.css("font-size");
    }
}
