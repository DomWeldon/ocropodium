var transcript = null;
var sdviewer = null;
var formatter = null;
var polltimeout = -1;


function onBinaryFetchResult(data) {


}

function pollForResults(data, polltime) {
    if (data == null) {
        alert("Return data is null!");
    } else if (data.error) {
        alert(data.error);
    } else if (data.status == "PENDING") {
        $.ajax({
            url: "/batch/viewer_binarization_results/" + data.job_name + "/",
            dataType: "json",
            beforeSend: function(e) {
                sdviewer.setWaiting(true);
            },
            success: function(data) {
                if (polltimeout != -1) {
                    clearTimeout(polltimeout);
                    polltimeout = -1;
                }
                polltimeout = setTimeout(function() {
                    pollForResults(data, polltime);
                }, polltime);        
            },
            error: function(e) {
                alert(e);
            },
        });
    } else if (data.status == "SUCCESS") {
        $(sdviewer).data("binpath", data.results.out);
        sdviewer.setSource(data.results.src);
        sdviewer.setOutput(data.results.dst);
        sdviewer.setWaiting(false);
    }
}


$(function() {
    // setup toolbar
    $("#spellcheck").button();
    $("#format").buttonset();
    $("#next_page").button({
        text: false,
        icons: {
            primary: "ui-icon-seek-next",
        },
    });
    $("#prev_page").button({
        disabled: true,
        text: false,
        icons: {
            primary: "ui-icon-seek-prev",
        },
    });
    $("#save_data").button({
        disabled: true,
        text: false,
        icons: {
            primary: "ui-icon-disk",
        },
    });
    $("#save_training_data").button({
        text: false,
        icons: {
            primary: "ui-icon-check",
        },
    });
    $("#vlink").buttonset();

    $("#format_block").click(function(event) {
        formatter.blockLayout($(".transcript_lines"));
    });
    $("#format_line").click(function(event) {
        formatter.lineLayout($(".transcript_lines"));
    });
    $("#format_column").click(function(event) {
        formatter.columnLayout($(".transcript_lines"));
    });

    $("#page_slider").slider({min: 1, value: 1});

    transcript = new OcrTranscript("workspace", $("#batch_id").val(), $("#initial").val());   
    transcript.init();
    transcript.onBatchLoad = function() {
        $("#page_slider").slider({
            max: transcript.pageCount(),
            value: transcript.page() + 1,
        });
    }

    transcript.onPageChange = function() {
        var ismax = $("#page_slider").slider("option", "value") 
                == transcript.pageCount();
        var ismin = $("#page_slider").slider("option", "value") == 1; 
        $("#next_page").button({disabled: ismax});         
        $("#prev_page").button({disabled: ismin});
    }

    // When a page loads, read the data and request the source
    // image is rebinarized so we can view it in the viewer
    // This is likely to be horribly inefficient, at least
    // at first...
    transcript.onPageLoad = function() {

        // get should-be-hidden implementation details
        // i.e. the task id that process the page.  We
        // want to rebinarize with the same params
        var task_pk = transcript.pageData().pk;
        $.ajax({
            url: "/batch/submit_viewer_binarization/" + task_pk + "/",
            dataType: "json",
            beforeSend: function(e) {
                sdviewer.close();
                sdviewer.setWaiting(true);
            },
            success: function(data) {
                if (polltimeout != -1) {
                    clearTimeout(polltimeout);
                    polltimeout = -1;
                }
                pollForResults(data, 300);
            },
            error: function(e) {
                alert(e);
            },
        });
    }

    transcript.onTextChanged = function() {
        $("#save_data").button({
            disabled: false,
        });
    }

    transcript.onSave = function() {
        $("#save_data").button({
            disabled: true,
        });
    }

    transcript.onLinesReady = function() {
        // trigger a reformat
        $("input[name=format]:checked").click();
    }

    var positionViewer = function(position) {
        // ensure the given line is centred in the viewport
        var bounds = transcript.pageData().fields.results.box;
        var fw = bounds[2], fh = bounds[3];
        var x = position[0], y = position[1], w = position[2], h = position[3];        
        var rect = new Seadragon.Rect(x / fw, (y - h) / fw, w / fw, h / fw);
        var overlaydiv = document.createElement("div");
        $(overlaydiv).addClass("viewer_highlight");
        sdviewer.activeViewer().viewport.fitBounds(rect, true);
        sdviewer.activeViewer().drawer.clearOverlays(); 
        sdviewer.activeViewer().drawer.addOverlay(overlaydiv, rect);         
    }

    transcript.onHoverPosition = function(position) {
        if (!($("input[name=vlink]:checked").val() == "hover" 
                    && sdviewer.activeViewer().viewport))
            return;
        positionViewer(position);
    }

    transcript.onClickPosition = function(position) {
        if (!($("input[name=vlink]:checked").val() == "click" 
                    && sdviewer.activeViewer().viewport))
            return;
        positionViewer(position);
    }

    $("#spellcheck").change(function(event) {
        if ($(this).attr("checked")) {
            transcript.startSpellcheck();
        } else {
            transcript.endSpellcheck();
        }
    });

    $("#save_data").click(function(event) {
        transcript.save();
    });

    $("#save_training_data").click(function(event) {
        var pk = transcript.pageData().pk;
        var binurl = $(sdviewer).data("binpath");
        $.ajax({
            url: "/training/save_task/" + pk + "/",
            data: {binary_image: binurl},
            dataType: "json",
            type: "POST",
            error: function(xhr, err, str) {
                alert(err + "  " + str);
            },
            success: function(data) {
                if (data.error)
                    return alert("Error: " + data.error);
                alert("Saved!");
            },
            complete: function() {

            },
        });
    });

    $("#page_slider").slider({
        stop: function(e, ui) {
            transcript.setPage($("#page_slider").slider("option", "value") - 1);
        },
        
    });

    $("#prev_page").click(function(event) {
        var curr = $("#page_slider").slider("option", "value");
        $("#page_slider").slider("option", "value", curr - 1);
    });

    $("#next_page").click(function(event) {
        var curr = $("#page_slider").slider("option", "value");
        $("#page_slider").slider("option", "value", curr + 1);
    });
    
    // line formatter object
    formatter = new OcrLineFormatter();
    
    // viewer object
    sdviewer = new ImageWindow("sideviewer"); 
    sdviewer.init();

    //layoutWidgets();

    // maximise the height of the transcript page
    maximiseWidgets(transcript, sdviewer);
    $(window).resize(function(event) {
        maximiseWidgets(transcript, sdviewer);
    });
});        

