// Object to represent and display a page of OCR data that's being 
// processed by the server.  The server passes back a list of 'page
// jobs' from which can be derived the page and job names.  
//
//  {
//      job_name: "simple.png::2f80247a-85b4-11df-8309-002564d1c84c",
//      status:   "PENDING",
//      results:  null,
//  }
//
//
// This object then creates an HTML container for the data and 
// repeatedly polls /batch/results/<batch-pk> until to status
// changes (to SUCCESS or ERROR) at which point to displays
// whatever is in 'results'.

function OcrBatch(insertinto_id, batch_id) {
    var m_batch_id = batch_id;

    // time to recheck running tasks
    var m_polltime = 500; 

    // max number of tasks to load
    var m_maxtasks = 15;

    // start of first loaded task
    var m_taskoffset = 0;

    // cache of data, initially empty
    var m_batchdata = null;

    // store the id for the next timeout
    var m_polltimeout = -1;

    // alias 'this' for use from within callbacks
    var self = this;

    // UI bits it's useful to keep a reference to:
    var m_container = $("<div></div>")
        .addClass("widget");  
    var m_header = $("<div></div>")
        .addClass("batch_head")
        .addClass("widget_header")
        .attr("id", "batch_head");
    var m_batchdiv = $("<div></div>")
        .addClass("ocr_page")
        .addClass("waiting")
        .attr("id", "ocr_page");

    var m_scrollwin = $("<span></span>")
        .addClass("scroll_viewer")
        .attr("id", "scroll_viewer");


    this.buildUi = function() {
        // create container structure
        createBatchHeaderUi();    
        createTaskListUi();
        // add the containter to the
        m_container.append(m_header).append(m_batchdiv).appendTo("#" + insertinto_id);
    }



    this.init = function() {
        self.buildUi();
        manualRefresh();
    }


    this.setBatchId = function(batch_id) {
        m_batch_id = batch_id;
        if (self.isComplete()) {
            manualRefresh();
        }
    }


    /*
     *  Events
     */

    $(".batch_name").live("click", function(event) {
        $(this).toggleClass("expanded");
        m_batchdiv.find(".tl_container").toggle();
        setScrollHandleHeight();
    });


    $(".retry_task").live("click", function(event) {
        var pk = $(this).data("pk");
        $.ajax({
            url: "/batch/retry_task/" + pk + "/",
            type: "POST",
            dataType: "json",
            success: function(data) {
                if (data.ok) {
                }
                manualRefresh();                
            },
        });
        event.preventDefault();    
    });


    $(".abort_task").live("click", function(event) {
        var pk = $(this).data("pk");
        $.ajax({
            url: "/batch/abort_task/" + pk + "/",
            type: "POST",
            dataType: "json",
            success: function(data) {
                if (data.ok) {
                } else {
                }
                manualRefresh();                
            },
        });
        event.preventDefault();    
    });


    $(".abort_batch").live("click", function(event) {
        var pk = $(this).data("pk");
        $.ajax({
            url: "/batch/abort_batch/" + pk + "/",
            type: "POST",
            dataType: "json",
            success: function(data) {
                if (data.ok) {
                } else {
                }
                manualRefresh();                
            },
        });
        event.preventDefault();    
    });


    $("#scrolldown").live("click", function(event) {
        m_taskoffset = Math.min(
            m_batchdata.extras.task_count - m_maxtasks, 
            m_taskoffset + 1);
        if (self.isComplete()) {
            manualRefresh();
        }
        setScrollHandlePosition();        
    });

    $("#scrollup").live("click", function(event) {
        m_taskoffset = Math.max(0, m_taskoffset - 1);
        if (self.isComplete()) {
            manualRefresh();
        }        
        setScrollHandlePosition();        
    });


    $(".retry_batch").live("click", function(event) {
        var pk = $(this).data("pk");
        $.ajax({
            url: "/batch/retry_batch/" + pk + "/",
            type: "POST",
            dataType: "json",
            success: function(data) {
                if (data.ok) {
                }
                manualRefresh();                
            },
        });
        event.preventDefault();   
        event.stopPropagation(); 
    });

    var setScrollHandlePosition = function() {
        var bar = $("#scrollbar");
        var handle = $("#scrollhandle");
        var offset = Math.floor(handle.height() / 2);
        var start = bar.position().top + offset;
        var end = bar.position().top + bar.height() - offset;
        var range = end - start + 1;

        // shortcuts for top and bottom of range 
        if (m_taskoffset == 0) {
            handle.css("top", "0px");
        } else if (m_taskoffset + m_maxtasks == m_batchdata.extras.task_count) {
            handle.css("top", ( bar.height() - handle.height() ) + "px");
        } else {
            var maxoffset = m_batchdata.extras.task_count - m_maxtasks;
            var current = (m_taskoffset / maxoffset) * range;
            handle.css("top", current + "px");
        }
    }


    var onScroll = function(event, ui) {
        // work out where we are in the div
        var bar = $("#scrollbar");
        var handle = $("#scrollhandle");
        var offset = Math.floor(handle.height() / 2);
        var start = bar.position().top + offset;
        var current = handle.position().top + offset - start;
        var end = bar.position().top + bar.height() - offset;
        var range = end - start + 1;
        var percent =  (current / range) * 100;

        var maxoffset = m_batchdata.extras.task_count - m_maxtasks;
        m_taskoffset = Math.round(maxoffset * (current / range));
        // clamp it's range
        m_taskoffset = Math.min(maxoffset, m_taskoffset);
        m_taskoffset = Math.max(0, m_taskoffset);
        m_scrollwin.text("Task " + (m_taskoffset + 1)); 
    }

    var onScrollStart = function(event, ui) {
        $("body").append(m_scrollwin);
        var tasklist = $(".task_list");
        m_scrollwin
            .show()
            .css("top", tasklist.position().top + 20)
            .css("left", tasklist.position().left + 20);

    }

    var onScrollStop = function(event, ui) {
        m_scrollwin.remove();
        if (self.isComplete()) {
            manualRefresh();
        }
    }

    var updateScrollButtons = function(event) {
    }


    var createBatchHeaderUi = function() {
        var batch = $("<div></div>")
            .addClass("batch")
            .addClass("expanded");
        batch.append(
            $("<span></span>")
                .addClass("batch_name")
                .text("Batch"));
        addProgressBar(batch);
        batch.append(
            $("<span></span>")
                .addClass("page_info"));
        batch.append(
            $("<a></a>")
                .attr("href", "#")
                .addClass("retry_batch")
                .text("Retry All"));
        batch.append(
            $("<a></a>")
                .attr("href", "#")
                .addClass("abort_batch")
                .text("Abort Batch"));
        m_batchdiv.append(batch);
    }


    var createTaskListUi = function() {
        var tlcontainer = $("<div></div>")
            .addClass("tl_container");
        var tlscrollcontainer = $("<div></div>")
            .addClass("tl_scrollcontainer");
        var scrollup = $("<div></div>")
            .addClass("tl_scrollup")
            .attr("id", "scrollup");
        var scrollbar = $("<div></div>")
            .addClass("tl_scrollbar")
            .attr("id", "scrollbar");
        var scrolldown = $("<div></div>")
            .addClass("tl_scrolldown")
            .attr("id", "scrolldown");
        var scrollhandle = $("<div></div>")
            .addClass("tl_scrollhandle")
            .attr("id", "scrollhandle")
            .draggable({
                containment: "parent",
                axis: "y",
                start: onScrollStart,
                drag: onScroll,
                stop: onScrollStop,
            });
        tlscrollcontainer
            .append(scrollup)
            .append(scrollbar.append(scrollhandle))
            .append(scrolldown)
            .appendTo(tlcontainer);

        var tasklist = $("<div></div>")
            .addClass("task_list");
        tlcontainer.append(tasklist);

        var task = $("<div></div>")
            .addClass("batch_task")
            .hide();
        task.append(
            $("<span></span>")
                .addClass("page_name"));
        addProgressBar(task);
        task.append(
            $("<a></a>")
                .attr("href", "#")
                .addClass("retry_task")
                .text("Retry"));
        task.append(
            $("<a></a>")
                .attr("href", "#")
                .addClass("abort_task")
                .text("Abort"));
        task.append(
            $("<span></span>")
                .addClass("page_info"));
        for (var i = 0; i < m_maxtasks; i++) {
            tasklist.append(task.clone());
        }

        m_batchdiv.append(tlcontainer);        
    }


    var setBatchResults = function(batchdata) {
        var batch = m_batchdiv.find(".batch");
        batch.attr("id", "batch" + batchdata.pk)

        // set titles
        batch.find("#batch_head, .batch_name").text(batchdata.fields.name);

        // update links with the batch id
        batch.find(".retry_batch")
            .attr("href", "/batch/retry_batch/" + batchdata.pk + "/") 
            .data("pk", batchdata.pk);
        batch.find(".abort_batch")
            .attr("href", "/batch/abort_batch/" + batchdata.pk + "/") 
            .data("pk", batchdata.pk);
        setProgressStatus(batch, batchdata.extras.estimate_progress);
    }


    var setProgressStatus = function(task, progress, status) {
        task.find(".progress").css("width", progress + "%");
        if (status) {
            task.find(".progressbar").attr("class", "progressbar " + status.toLowerCase());
        } else if (progress > 99.5) {
            task.find(".progressbar").attr("class", "progressbar done");
        } else {
            task.find(".progressbar").attr("class", "progressbar running");
        }       
    }


    var addProgressBar = function(task) {
        var progressbar = $("<span></span>")
            .addClass("progressbar");
        var progress = $("<span></span>")
            .addClass("progress");
        task.append(progressbar.append(progress));
    }

    
    var toggleScrollBar = function(show) {
        if (show) {
            $(".tl_scrollcontainer").show(100);
            $(".task_list").css("margin-right", "15px");
        } else {
            $(".tl_scrollcontainer").hide(100);
            $(".task_list").css("margin-right", "0px");
        }
    }


    var setScrollHandleHeight = function() {
        // work out how big the scroll handle should be
        var taskcount = m_batchdata.extras.task_count;
        var percheight = m_maxtasks / taskcount;
        var pixheight = Math.max(30, $("#scrollbar").height() * percheight);
        $("#scrollhandle").animate({height: pixheight}, 100);

        // hide the scrollbar if necessary
        toggleScrollBar(taskcount > m_maxtasks);
    }

    // add results to the page.
    var updateResults = function(batchdata) {

        m_batchdiv.removeClass("waiting");
        setBatchResults(batchdata);
        setScrollHandleHeight();

        var tasklist = m_batchdiv.find(".task_list");        
        for (var i = 0; i < m_maxtasks; i++) {
            var taskdata = batchdata.fields.tasks[i];
            var task = tasklist.find(".batch_task").slice(i);
            // hide the task if we've run out of data - this happens
            // if there are less than m_maxtasks tasks in the set.
            if (taskdata == null) {
                task.hide()
                    .attr("id", null)
                    .find("a")
                    .removeData()
                    .attr("href", "#")
                    .end()
                    .find("page_name")
                    .text("");
                continue;                
            }

            task.attr("id", "task" + taskdata.pk)
            task.find(".page_name")
                .text(taskdata.fields.page_name);
            task.find("a").data("pk", taskdata.pk);
            task.find(".retry_task")
                .attr("href", "/batch/retry_task/" + taskdata.pk + "/");
            task.find(".abort_task")
                .attr("href", "/batch/abort_task/" + taskdata.pk + "/");
            setProgressStatus(task, taskdata.fields.progress, taskdata.fields.status);
            if (taskdata.fields.lines != null) {
                task.find(".page_info").text("Lines: " + taskdata.fields.lines);
            }
            task.show()
        }
    }


    // check whether all tasks are complete
    this.isComplete = function() {
        return m_batchdata.extras.is_complete;
    }

    this.updateResults = function() {
        updateResults();
    }

    // handle the results of each poll - we should
    // get back an array containing only one element
    // (due to the way django serializes our query
    var processData = function(data) {
        if (data.error) {
            setError(data.error, data.trace);
        } else {
            m_batchdata = data[0];
            updateResults(m_batchdata);
            return self.isComplete(); 
        }
        return true;
    }

    // set a waiting spinner when doing something
    this.setWaiting = function(waiting) {
        if (waiting) {
            m_batchdiv.addClass("waiting");
        } else {
            m_batchdiv.removeClass("waiting");
        }
    }

    
    // check the server for complete results...
    var pollForResults = function(polltime) {
        $.ajax({
            url: "/batch/results/" + m_batch_id,
            data: {start: m_taskoffset, limit: m_maxtasks},
            type: "GET",
            dataType: "json",
            success: function(data) {
                if (!processData(data)) {
                    m_polltimeout = setTimeout(function() {
                        pollForResults(polltime);
                    }, polltime);
                } else {
                    m_polltimeout = -1;
                }                
            },
            error: function(xhr, statusText, errorThrown) {
                setError("Http Error " + statusText, errorThrown);
            }
        }); 
    }

    // refresh immediately - cancel the next poll
    // and start a new one if necessary
    var manualRefresh = function() {
        if (m_polltimeout != -1) {
            clearTimeout(m_polltimeout);
        }
        pollForResults(m_polltime)
    }


    // wrapper for external access.  I don't really know why, but
    // if the Async function is called directly from this function
    // rather than the closure, async calls from multiple separate
    // objects seem to get jumbled up.
    this.pollForResults = function(polltime) {
        pollForResults(polltime);
    }
}
