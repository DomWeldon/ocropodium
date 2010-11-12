// Editor for text on a single OCR transcript line


function OcrLineEditor(insertinto_id) {
    "use strict"
    const LONGKEY = 500;
    const SHORTKEY = 70;
    const NAVKEYS  = [KC_LEFT, KC_RIGHT, KC_HOME, KC_END];
    const METAKEYS = [KC_ALT, KC_CTRL, KC_CAPSLOCK, KC_SHIFT];    
    
    var self = this,            // alias 'this' 
        m_elem = null,          // the element we're operating on 
        m_char = null,          // the current character in front of the cursor 
        m_selectstart = null,   // selection start & end  
        m_inittext = null,      // initial text of selected element 
        m_keyevent = null,      // capture the last key event 
        m_blinktimer = -1,      // timer for cursor flashing
        m_dragpoint = null,     // the point dragging started 
        m_undostack = new OCRJS.UndoStack(this), // undo stack object 
        m_cursor = $("<div></div>") // cursor element
            .addClass("editcursor")
            .text("|"),
        m_endmarker = $("<div></div>")  // anchor for the end of the line 
            .addClass("endmarker"),

        // lookup for key navigation functions
        m_navtable = {
            KC_LEFT: self.moveCursorLeft,
            KC_RIGHT: self.moveCursorRight,
            KC_HOME:  self.moveCursorToStart,
            KC_END: self.moveCursorToEnd,
        };



    // functions

    var blinkCursor = function(blink) {
        if (blink) {
            m_cursor.toggleClass("blink");
            m_blinktimer = setTimeout(function() {
                blinkCursor(true);        
            }, LONGKEY);
        } else {
            clearTimeout(m_blinktimer);
            m_blinktimer = -1;
        }
    }

    // Undoable commands - note that these depend
    // on the outer object scope, which is not ideal
    var InsertCommand = OCRJS.UndoCommand.extend({
        constructor: function(char, curr) {
            this.base("typing");
            this.curr = curr;
            this.char = char;
            var self = this;
            this.redo = function() {
                self.char.insertBefore(self.curr);
                positionCursorTo(self.curr);
            };
            this.undo = function() {
                self.char.remove();
                m_char = self.curr;
                positionCursorTo(self.curr);
            };
            this.mergeWith = function(other) {
                self.char = self.char.add(other.char.get());                    
                return true;                
            };
        },
    });

    var DeleteCommand = OCRJS.UndoCommand.extend({
        constructor: function(elems, nexts, back) {
            this.base("delete");
            this.elems = elems;
            this.nexts = nexts;
            this.back = back;
            var self = this;
            this.redo = function() {
                $(self.elems).not(".endmarker").detach();
                m_char = self.nexts[0];
                positionCursorTo(m_char);
            };
            this.undo = function() {
                for (var i in self.elems) {
                    $(self.elems[i]).insertBefore(self.nexts[i]);
                    m_char = self.back 
                            ? self.elems[i].nextElementSibling : self.elems[i];
                    positionCursorTo(m_char);
                }
            };
            this.mergeWith = function(other) {
                for (var i in other.elems) {
                    self.elems.push(other.elems[i]);
                    self.nexts.push(other.nexts[i]);
                }
                return true;    
            };
        },
    });

    var positionCursorTo = function(elem) {
        var mintop = $(m_elem).offset().top;
        var minleft = $(m_elem).offset().left;
        // anchor to either the prev element or the parent.  This is to
        // hack around the fact that breaking chars (spaces) in Webkit
        // seem to have no position
        if (elem && elem.previousElementSibling) {
            var prev = $(elem.previousElementSibling);
            mintop = Math.max(mintop, prev.offset().top);
            minleft = Math.max(minleft, prev.offset().left
                   + prev.width());
        }
        // if there's no char elem, set to back of
        // the container box
        if (!elem || elem.tagName == "DIV") {
            var top = m_endmarker.offset().top;
            // hack around Firefox float drop bug
            if ($.browser.mozilla) {
                if ($(m_elem).children().length > 1) {
                    top = $(m_elem).children().slice(-2).offset().top;
                } else {
                    top = ($(m_elem).offset().top + $(m_elem).height()) - m_endmarker.height();
                }
            }
            m_cursor
                .css("top", top + "px")
                .css("left", (m_endmarker.offset().left + m_endmarker.width()) + "px");
            return;
        }

        var top = Math.max(mintop, $(elem).offset().top);
        var left = Math.max(minleft, $(elem).offset().left);
        m_cursor.css("top", top + "px").css("left", left + "px");
    }

    var deselectAll = function() {
        m_selectstart = null;
        var done = $(m_elem).children(".sl").length > 0;
        $(m_elem).children().removeClass("sl");
        return done;
    }

    var keyNav = function(code) {
        m_undostack.breakCompression();
        if (!m_keyevent.shiftKey) {
            deselectAll();
        } else {
            if (m_selectstart == null)
                m_selectstart = m_char;
        }

        if (code == KC_RIGHT) {
            moveCursorRight();
        } else if (code == KC_LEFT) {
            moveCursorLeft();
        } else if (code == KC_HOME)
            moveCursorToStart();
        else if (code == KC_END)
            moveCursorToEnd();
        if (m_keyevent.shiftKey)
            updateSelection(m_selectstart, m_char);
    }

    var updateSelection = function(s, e) {
        if (s == e) {
            $(m_elem).children().removeClass("sl");
            return;
        }
        var gotstart = false;
        for (var i = 0; i < m_elem.childElementCount; i++) {         
            if (m_elem.children[i] == s || m_elem.children[i] == e) {
                gotstart = !gotstart;
            }
            $(m_elem.children[i]).toggleClass("sl", gotstart);
        }
    }

    var moveCursorLeft = function() {
        if (!m_keyevent.shiftKey)
            deselectAll();
        
        // check if we're at the end
        // or at the beginning...
        if (!m_char) {
            m_char = $(m_elem).find("span").get(-1);            
        } else {
            var prev = m_char.previousElementSibling;
            if (!prev) {
                // we're already at the start
                return false;
            }
            m_char = prev;
        }
        positionCursorTo(m_char);
        return true;
    }

    var moveCursorRight = function() {
        if (!m_char)
            return false;
        m_char = m_char.nextElementSibling;
        // check if we're at the end
        positionCursorTo(m_char);
        return true;
    }

    var moveCursorToStart = function() {
        if (!m_keyevent.shiftKey)
            deselectAll();
        m_char = $(m_elem).children().get(0);
        positionCursorTo(m_char);
    }                   

    var moveCursorToEnd = function() {
        if (!m_keyevent.shiftKey)
            deselectAll();
        m_char = null;
        positionCursorTo(m_char);
    }

    var initialiseCursor = function(clickevent) {
        // find the first letter in the series (ignore spaces)
        m_char = $(m_elem).find("span").filter(function(index) {
            return $(this).text() != " ";                            
        }).get(0);
        positionCursorTo(m_char);
        $("body").append(m_cursor);
        blinkCursor(true);
    }

    var deleteChar = function(back) {
        if (eraseSelection())
            return;

        // if we're already at the end, return
        if (!back && !m_char)
            return;

        // if we're at the beginning, return
        if (back && m_char && !m_char.previousElementSibling)
            return;

        // if we're at the end and backspacing, move back and delete
        if (back && !m_char && $(m_elem).children("span").length) {
            back = false;
            m_char = $(m_elem).children("span").last().get(0);
        }

        var next = back ? m_char : m_char.nextElementSibling;
        var curr = back
            ? m_char.previousElementSibling 
            : m_char;
        m_undostack.push(new DeleteCommand([curr], [next], back));
    }

    var eraseSelection = function() {
        var delset = $(m_elem).children("span.sl");
        if (delset.length == 0)
            return false;
        m_char = delset.last().next().get(0);
        // if we're on a space boundary and the next character
        // after the selection is also a space, hoover it up
        // as well
        if (delset.first().prev().length) {
            if (delset.first().prev().text().match(/^\s$/)) {
                if ($(m_char).text().match(/^\s$/)) {
                    $(m_char).addClass(".sl");
                    m_char = m_char.nextElementSibling;
                }
            }
        }
        var elems = delset.not(".endmarker").get();
        elems.reverse();
        var nexts = [];
        for (var i in elems)
            nexts.push(elems[i].nextElementSibling);

        m_undostack.push(new DeleteCommand(elems, nexts, false));
        m_undostack.breakCompression();
        positionCursorTo(m_char);
        return true;
    }

    var insertChar = function() {
        var charcode = m_keyevent.which;        
        eraseSelection();
        
        var curr = m_char ? m_char : m_endmarker;
        var char = $("<span></span>")
            .text(m_keyevent.charCode == 32
                    ? "\u00a0"
                    : String.fromCharCode(m_keyevent.charCode));

        m_undostack.push(new InsertCommand(char, curr));
    }
    
    var backspace = function(event) {
        if (eraseSelection())
            return;
        deleteChar(true);
    }

    var keyPressDetection = function(event) {
        m_keyevent = event;

        // handle undo/redo with ctrl-z, ctrl-shift-z
        if (event.ctrlKey && event.which == 90) {
            if (!event.shiftKey) {
                m_undostack.undo();
            } else {
                m_undostack.redo();
            }
            event.preventDefault();
            return;    
        }

        if (event.ctrlKey || event.altKey)
            return;

        if ($.inArray(event.which, METAKEYS) != -1) {
            // do nothing!
        } else if (event.which == KC_TAB) {
            if (!event.shiftKey)             
                self.onEditNextElement();
            else
                self.onEditPrevElement();
            return false;
        } else if (event.which == KC_ESCAPE) {
            finishEditing(m_inittext);
        } else if (event.which == KC_RETURN) {
            finishEditing();
        } else if ($.inArray(event.which, NAVKEYS) != -1) {
            keyNav(event.which);
        } else if (event.which == KC_DELETE) {
            deleteChar();
        } else if (event.which == KC_BACKSPACE) {
            backspace();
        } else {
            return;
            //alert(event.which);
        }
        blinkCursor(false);    
        event.preventDefault();
    }

    var charClicked = function(event) {
        var offset = $(this).offset();            
        var mid = $(this).width() / 2;
        var atend = $(this).next().length == 0;

        // if we've clicked on the first char, position the
        // cursor, set the start marker
        if ($(this).prev().length == 0) {
            positionCursorTo($(this));
            return;    
        }

        // if we click on latter half of the last element
        if ($(this).next().length == 0 && event.pageX > (offset.left + mid)) {
            positionCursorTo($(this), true);
            return;
        }

        // otherwise, we're in the middle somewhere
        if (event.pageX > (offset.left + mid)) 
            m_char = this.nextElementSibling;
        else
            m_char = this;

        positionCursorTo(m_char);
    }

    var selectCurrentWord = function(event) {
        // this is TERRIBLE!  Whatever, too late, will
        // fix it in the cold light of day.
        deselectAll();
        if (!m_char)
            return;
        var startchar = m_char;
        while (startchar.previousElementSibling 
                && startchar.previousElementSibling.textContent.match(/^\w$/)) {
            startchar = startchar.previousElementSibling;
        }
        var endchar = m_char;        
        while (endchar && endchar != m_endmarker.get(0)
                && endchar.textContent.match(/^\w$/)) {
            endchar = endchar.nextElementSibling;
        }
        updateSelection(startchar, endchar);
    }

    var selectCharUnderClick = function(event) {
        if (!event)
            return;
        // find the 'new' span element that would've
        // been under the mouse when clicked
        for (var i = 0; i < $(m_elem).find("span").length; i++) {
            var elem = $(m_elem).find("span").slice(i);
            var elemoffset = elem.offset();
            if (event.pageX < elemoffset.left)
                continue;
            if (event.pageX > elemoffset.left + elem.width())
                continue;
            if (event.pageY < elemoffset.top)
                continue;
            if (event.pageY > elemoffset.top + elem.height())
                continue;
            m_char = elem.get(0);
            if (event.pageX > (elemoffset.left + (elem.width() / 2)))
                m_char = elem.next().get(0);
            break;
        }
        positionCursorTo(m_char);
        m_undostack.breakCompression();
    }


    var isCapslock = function (e) {
        e = (e) ? e : window.event;

        var charCode = false;
        if (e.which) {
            charCode = e.which;
        } else if (e.keyCode) {
            charCode = e.keyCode;
        }
        var shifton = false;
        if (e.shiftKey) {
            shifton = e.shiftKey;
        } else if (e.modifiers) {
            shifton = !!(e.modifiers & 4);
        }
        if (charCode >= 97 && charCode <= 122 && shifton) {
            return true;
        }
        if (charCode >= 65 && charCode <= 90 && !shifton) {
            return true;
        }

        return false;
    }

    var valueInRange = function(value, min, max) {
        return (value <= max) && (value >= min);
    }

    var rectOverlap = function(A, B) {
        var xOverlap = valueInRange(A.x, B.x, B.x + B.width) ||
            valueInRange(B.x, A.x, A.x + A.width);
        var yOverlap = valueInRange(A.y, B.y, B.y + B.height) ||
            valueInRange(B.y, A.y, A.y + A.height);
        return xOverlap && yOverlap;
    }


    var expandSelectedChars = function(moveevent) {
        if (!m_dragpoint)
            return;
        // create a normalised rect from the current
        // point and the m_dragpoint
        //
        var x0 = Math.min(m_dragpoint.x, moveevent.pageX),
            x1 = Math.max(m_dragpoint.x, moveevent.pageX),
            y0 = Math.min(m_dragpoint.y, moveevent.pageY),
            y1 = Math.max(m_dragpoint.y, moveevent.pageY);
        var cbox = {x: x0, y: y1, width: x1 - x0, height: y1 - y0},
            span = $(m_elem).get(0),
            cr,
            box;
        for (var i = 0; i < span.childElementCount; i++) {
            cr = span.children[i].getClientRects()[0];
            box = {
                x: cr.left,
                y: cr.top,
                width: cr.right - cr.left, 
                height: cr.bottom - cr.top,
            }
            $(span.children[i]).toggleClass("sl", rectOverlap(cbox, box));
        }
    }


    var finishEditing = function(withtext) {
        var element = $(m_elem);
        releaseElement(withtext);
        self.onEditingFinished(element);
    }


    this.setElement = function(element, clickevent) {
        if (m_elem != null) {
            releaseElement();
        }
        m_elem = element;
        m_inittext = $(m_elem).text();        
        grabElement(clickevent);
        self.onEditingStarted(element);
    }

    this.element = function() {
        return $(m_elem);
    }

    var grabElement = function(clickevent) {
        $(m_elem).addClass("selected");    
        $(m_elem).addClass("editing");
        
        // wrap a span round each char
        $(m_elem).html($.map($.trim($(m_elem).text()), function(ch) {
            return "<span>" + ch + "</span>";
        }).join("")).append(
            m_endmarker.height($(m_elem).height())
        );

        // set up a click handler for the window
        // if we click outside the current element, 
        // close the editor and unbind the click
        $(window).bind("click.editorblur", function(event) {
            var left = $(m_elem).offset().left;
            var top = $(m_elem).offset().top;
            var width = $(m_elem).outerWidth();
            var height = $(m_elem).outerHeight();

            if (!(event.pageX >= left 
                    && event.pageX <= (left + $(m_elem).width())
                    && event.pageY >= top
                    && event.pageY <= (top + $(m_elem).height()))) {
                finishEditing();
            }
        });

        $(window).bind("keydown.editortype", keyPressDetection);
        $(window).bind("keypress.editortype", function(event) {
            if (event.ctrlKey || event.charCode == 0)
                return true;
            m_keyevent = event;
            insertChar();
            event.preventDefault();        
        });
        window.getSelection().removeAllRanges();
                
        // bind mouse up to override selection
        $(window).bind("mouseup.checkselection", function(event) {
            $(window).unbind("mousemove.noselection");
            return false;
        });

        $(m_elem).bind("mousedown.noselection", function(event) {
            $(window).bind("mousemove.noselection", function(event) {
                window.getSelection().removeAllRanges();
            });
        });

        // handler to track mouse moves when selecting text
        $(m_elem).bind("mousedown.selecttext", function(event) {
            // not sure why this happens, but sometimes the
            // selecttext bind errors...
            if (!m_elem)
                return;
            m_dragpoint = { x: event.pageX, y: event.pageY };
            $(m_elem).bind("mousemove.selecttext", function(event) {
                expandSelectedChars(event);                
            });
            $(window).bind("mouseup.selecttext", function(event) {
                $(m_elem).unbind("mousemove.selecttext");
                $(window).unbind("mouseup.selecttext");
                m_dragpoint = null;
            });            
        });

        $(m_elem).bind("dblclick.selectword", function(event) {
            window.getSelection().removeAllRanges();
            selectCurrentWord();
        });

        $(window).bind("keyup.editortype", function(event) {
            if (m_blinktimer == -1)
                blinkCursor(true);
        });

        $(m_elem).find("span").live("click.positioncursor", charClicked);
        $(m_elem).find("span").live("click.clearselect", deselectAll);

        initialiseCursor();
        selectCharUnderClick(clickevent);
    }


    var releaseElement = function(settext) {
        $(m_elem).children()
            .die("click.clearselect")
            .die("click.positioncursor");
        $(m_elem)
            .html(settext ? settext : $(m_elem).text())
            .removeClass("selected")
            .removeClass("editing")
            .unbind("dblclick.selectword")
            .unbind("mousedown.noselection")
            .unbind("mousemove.selecttext")
            .unbind("mouseup.textsel");
        $(window)
            .unbind("click.editorblur")
            .unbind("keydown.editortype")
            .unbind("keypress.editortype")
            .unbind("keyup.editortype")
            .unbind("mousemove.noselection")
            .unbind("mouseup.checkselection")
            .unbind("mouseup.selecttext");
        $(m_elem).unbind("mousedown.noselection");

        m_char = null;
        m_selectstart = null;        
        m_elem = null;
        blinkCursor(false);
        m_cursor.remove();
    }
}

OcrLineEditor.prototype.onEditNextElement = function(event) {

}

OcrLineEditor.prototype.onEditPrevElement = function(event) {

}

OcrLineEditor.prototype.onEditingStarted = function(event) {

}

OcrLineEditor.prototype.onEditingFinished = function(event) {

}

