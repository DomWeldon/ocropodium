// Make a span editable.  Second attempt


if (OcrJs === undefined) {
    var OcrJs = {};
}


// Jquery, disallow selection
jQuery.fn.extend({
    allowSelection : function(allow) {
        this.each(function() {
            this.onselectstart = function() { return allow; };
            this.unselectable = allow ? "" : "on";
            jQuery(this).css('-moz-user-select', allow ?  null : 'none');
        });
        return this;
    }
});




/*
 * Undo Commands for insert/delete
 *
 */

var InsertCommand = OcrJs.UndoCommand.extend({
    init: function(editor, chars, curr) {
        this._super("typing");
        this.editor = editor;
        this.curr = curr;
        this.chars = chars;
        var self = this;
        this.redo = function() {
            
            $(self.chars).insertBefore(self.curr);
            // hack around Chrome not doing a reflow when inserting
            // after a breaking element - toggle overflow to force it
            if ($.browser.webkit && self.editor.isWrapping()) {
                $(self.curr).css("overflow", "auto");
                setTimeout(function() {
                    $(self.curr).css("overflow", null);
                }, 0);
            }
            self.editor.setCurrentChar(self.curr);
        };
        this.undo = function() {
            $(self.chars).remove();
            self.editor.setCurrentChar(self.curr);
        };
        this.mergeWith = function(other) {
            self.chars = $(self.chars).add(other.chars).get();
            return true;
        };
    },
});

var DeleteCommand = OcrJs.UndoCommand.extend({
    init: function(editor, elems, nexts, back) {
        this._super("delete");
        this.editor = editor;
        this.elems = elems;
        this.nexts = nexts;
        this.back = back;
        var self = this;
        this.redo = function() {
            $(self.elems).not(".endmarker").detach();
            self.editor.setCurrentChar(self.nexts[0]);
        };
        this.undo = function() {
            for (var i in self.elems) {
                $(self.elems[i]).insertBefore(self.nexts[i]);
                self.editor.setCurrentChar(self.back
                        ? self.elems[i].nextElementSibling : self.elems[i]);
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


const LONGKEY = 500;
OcrJs.LineEditor = OcrJs.Base.extend({
    init: function(options) {
        this._super();
        this.options = {log: false};
        $.extend(this.options, options);

        this._listeners = {
            onEditNextElement: [],
            onEditPrevElement: [],
            onEditingStarted: [],
            onEditingFinished: [],
        };

        this._e = null;          // the element we're operating on
        this._c = null;          // the current character in front of the cursor
        this._top = null;         // reference to initial top of elem
        this._left = null;        // reference to initial left of elem
        this._selectstart = null;   // selection start & end
        this._inittext = null;      // initial text of selected element
        this._keyevent = null;      // capture the last key event
        this._blinktimer = -1;      // timer for cursor flashing
        this._dragpoint = null;     // the point dragging started
        this._editing = false;      // we're currently doing something
        this._undostack = new OcrJs.UndoStack(this); // undo stack object
        this._notemptyre = new RegExp("\S");
        this._cursor = $("<div></div>") // cursor element
                .addClass("editcursor")
                .text("").get(0);
        this._endmarker = $("<div></div>")  // anchor for the end of the line
                .addClass("endmarker").get(0);
        this._keyhacks = {
            190: [62, 46],
            57:  [40, 57],
            55:  [38, 55],
            53:  [37, 53],
            52:  [36, 52],
            222: [39, 39],
        }


    },

    /*
     * Setup and teardown functions
     *
     */

    edit: function(elem, event) {
        if (this._editing)
            this.finishEditing();
        if (!elem)
            throw "Attempt to edit null element";
        this._e = elem;
        this._inittext = $(elem).text();
        this._editing = true;

        this.setupEvents()

        // wrap a span round each char
        $(this._e).html($.map($.trim($(this._e).text()), function(ch) {
            return "<span>" + ch + "</span>";
        }).join("")).append(
            $(this._endmarker).height($(this._e).height())
        );

        // set initial position of first element so we can later
        // anchor the line if necessary
        this._top = $(elem).children().first().offset().top;
        this._left = $(elem).children().first().offset().left;

        $(elem)
            .addClass("ui-selected")
            .addClass("editing")
            .allowSelection(false);

        this._initialiseCursor();
        if (event && event.type.match(/click/))
            this._selectCharUnderPoint(event);
        this.trigger("onEditingStarted", elem);
    },


    finishEditing: function(withtext) {
        var endtext = $(this._e).text();
        $(this._e)
            .removeClass("ui-selected")
            .removeClass("editing")
            .allowSelection(true)
            .html(this._inittext);
        this._selectstart = null;
        $(this._cursor).detach();
        this._undostack.clear();
        if (this._blinktimer != -1) {
            clearTimeout(this._blinktimer);
            this._blinkcursor = -1;
        }
        this.teardownEvents();
        this._editing = false;
        this.trigger("onEditingFinished",
            this._e,
            this._inittext,
            withtext ? withtext : endtext
        );
    },


    setCurrentChar: function(charelem) {
        if (!$.inArray(this._e.children, charelem))
            throw "Char element is not a childen of line";
        if (!charelem)
            throw "Attempt to set null element as current char";
        this._c = charelem;
        this._mungeSpaces();
        this.positionCursorTo(this._c);
        //console.log("Current char: " + $(this._c).text() + " Full: " + $(this._e).text());
        //console.log("Current char: " + $(this._c).text());
    },


    element: function() {
        return this._e;
    },


    setupEvents: function() {
        var self = this;
        var elem = this._e;

        // set up a click handler for the window
        // if we click outside the current element,
        // close the editor and unbind the click
        $(window).bind("click.editorblur", function(event) {
            var left = $(elem).offset().left;
            var top = $(elem).offset().top;
            var width = $(elem).outerWidth();
            var height = $(elem).outerHeight();

            if (!(event.pageX >= left
                    && event.pageX <= (left + $(elem).width())
                    && event.pageY >= top
                    && event.pageY <= (top + $(elem).height()))) {
                self.finishEditing();
            }
        });

        $(window).bind("keydown.editortype", function(event) {
            self.blinkCursor(false);
            if (self._handleKeyEvent(event)) {
                event.preventDefault();
                return false;
            }
        });

        $(window).bind("keypress.editortype", function(event) {
            if (self._handleKeyEvent(event)) {
                //self.blinkCursor(false);
                event.preventDefault();
                return false;
            }
        });

        $(window).bind("keyup.editortype", function(event) {
            if (self._blinktimer == -1) {
                self._blinktimer = setTimeout(function() {
                    self.blinkCursor(true);
                }, 2 * LONGKEY);
            }
        });

        // Mouse events
        $(this._e).find("span").live("click.positioncursor", function(event) {
            self._charClicked(event);
        });
        $(this._e).find("span").live("click.clearselect", function(event) {
            self.deselectAll();
        });
        $(this._e).bind("dblclick.selectword", function(event) {
            self._selectCurrentWord(event);
        });
        // handler to track mouse moves when selecting text
        $(this._e).bind("mousedown.selecttext", function(event) {
            self.deselectAll();
            self._dragpoint = { x: event.pageX, y: event.pageY };
            $(self._e).bind("mousemove.selecttext", function(event) {
                //self._expandSelectedChars(event);
                self._selectCharUnderPoint(event);
            });
            $(window).bind("mouseup.selecttext", function(event) {
                $(self._e).unbind("mousemove.selecttext");
                $(window).unbind("mouseup.selecttext");
                self._dragpoint = null;
            });
        });
    },


    teardownEvents: function() {
        $(this._e).children()
            .die("click.clearselect")
            .die("click.positioncursor");
        $(this._e)
            .unbind("dblclick.selectword")
            .unbind("mousedown.noselection")
            .unbind("mousemove.selecttext");
        $(window)
            .unbind("click.editorblur")
            .unbind("keydown.editortype")
            .unbind("keypress.editortype")
            .unbind("keyup.editortype")
            .unbind("mouseup.selecttext");
    },


    /*
     * Cursor navigation and positioning functions
     *
     */

    // when at the end of the line, the current
    // char is the endmarker div.  This should
    // never be deleted
    isAtEnd: function() {
        return this._c.tagName == "DIV";
    },

    // determine if the line is wrapping.  Assumes
    // there are a least 2 chars (+ the endmarker)
    isWrapping: function() {
        if (this._e.children < 3)
            return false;
        var first = $(this._e).children().first().get(0);
        var last = this._endmarker.previousElementSibling;
        return $(first).offset().top != $(last).offset().top;
    },
                    
    moveCursorLeft: function() {
        // check if we're at the end
        // or at the beginning...
        if (!this._c.previousElementSibling)
            return;
        this.setCurrentChar(this._c.previousElementSibling);
        return true;
    },

    moveCursorRight: function() {
        if (this.isAtEnd())
            return false;
        this.setCurrentChar(this._c.nextElementSibling);
        return true;
    },

    moveCursorToStart: function() {
        console.log($(this._e).text());
        var char = $(this._e).children().first().get(0);
        if (!char)
            throw "First child of elem is null: " + this._e.firstChild + "  (" + this._e + ")";
        this.setCurrentChar(char);
    },

    moveCursorToEnd: function() {
        this.setCurrentChar(this._endmarker);
    },

    positionCursorTo: function(elem) {
        if (!elem)
            throw "Attempt to position cursor to null element";
        var os = this._elementPos(elem);
        if (elem.tagName == "DIV") {
            if (elem.previousElementSibling) {
                var neartext = $(elem).prevAll().filter(function(index) {
                    return $(this).text() != " ";
                }).first();
                if (neartext.length) {
                    os.top = neartext.offset().top;
                } else {
                    os.top = this._elementPos(this._e).top;
                }
            } else {
                os.top = this._top;
                os.left = this._left;
            }
        }

        $(this._cursor).css("top", os.top + "px").css("left", os.left + "px");
    },


    blinkCursor: function(blink) {
        var self = this;
        if (blink) {
            $(self._cursor).toggleClass("blinkoff");
            self._blinktimer = setTimeout(function() {
                self.blinkCursor(true);
            }, LONGKEY);
        } else {
            $(self._cursor).removeClass("blinkoff");
            clearTimeout(self._blinktimer);
            self._blinktimer = -1;
        }
    },


    /*
     * Selection functions
     *
     */

    deselectAll: function() {
        this._selectstart = null;
        var done = $(this._e).children(".sl").length > 0;
        $(this._e).children().removeClass("sl");
        return done;
    },

    updateSelection: function(start, end) {
        // FIXME: the element is weirdly borked the first time it's
        // accessed (childElementCount and the children array don't
        // work.  Hack around this by resetting it...???
        this._e = $(this._e).get(0);
        if (start == end) {
            $(this._e).children().removeClass("sl");
            return;
        }
        var gotstart = false;
        for (var i = 0; i < $(this._e).children().length; i++) {
            if (this._e.children[i] == start || this._e.children[i] == end) {
                gotstart = !gotstart;
            }
            $(this._e.children[i]).toggleClass("sl", gotstart);
        }
    },


    /*
     * Editing Function
     *
     */
    deleteChar: function(back) {
        if (this.eraseSelection())
            return;

        // if we're already at the end, return
        if (!back && !this._c)
            return;

        // if we're at the beginning, return
        if (back && this._c && !this._c.previousElementSibling)
            return;

        // if we're at the end and backspacing, move back and delete
        if (back && !this._c && $(this._e).children("span").length) {
            back = false;
            this._c = $(this._e).children("span").last().get(0);
        }

        var next = back ? this._c : this._c.nextElementSibling;
        var curr = back
            ? this._c.previousElementSibling
            : this._c;
        if (!curr)
            return;
        this._undostack.push(new DeleteCommand(this, [curr], [next], back));
    },


    eraseSelection: function() {
        var delset = $(this._e).children("span.sl");
        if (delset.length == 0)
            return false;
        this._c = delset.last().next().get(0);
        // if we're on a space boundary and the next character
        // after the selection is also a space, hoover it up
        // as well
        if (delset.first().prev().length) {
            if (delset.first().prev().text().match(/^\s$/)) {
                if ($(this._c).text().match(/^\s$/)) {
                    $(this._c).addClass(".sl");
                    this._c = this._c.nextElementSibling;
                }
            }
        }
        var elems = delset.not(".endmarker").get();
        elems.reverse();
        var nexts = [];
        for (var i in elems)
            nexts.push(elems[i].nextElementSibling);
        this._undostack.push(new DeleteCommand(this, elems, nexts, false));
        this._undostack.breakCompression();
        this.positionCursorTo(this._c);
        return true;
    },

                      
    insertChar: function(event) {
        this.eraseSelection();

        // FIXME: Hack for converting webkit keypress
        // deletes into periods, and adjusting the charcode
        // accordingly.  JS keyCodes are a total mess, but
        // there's got to be a better way.
        if ($.browser.webkit) {
            var hack = this._keyhacks[event.which];
            if (hack) {
                event.which = event.shiftKey ? hack[0] : hack[1];
            }
        }

        var curr = this._c ? this._c : this._endmarker;
        var char = $("<span></span>")
            .text(event.which == 32
                    ? "\u00a0"
                    : String.fromCharCode(event.which)).get(0);
        this._undostack.push(new InsertCommand(this, char, curr));
    },

    /*
     * Private Functions
     */

    // handle key event - return true IF the event
    // IS handled
    _handleKeyEvent: function(event) {
        console.log(event.keyCode);
        // BROWSER HACK - FIXME: Firefox only receives
        // repeat key events for keypress, but ALSO
        // fires keydown for non-char keys
        if (!$.browser.webkit) {
            if (!event.ctrlKey && event.type == "keydown")
                return;
        }

        // FIXME: Another chrome hack, to prevent the 'period' key
        // generating a keyCode 46 'delete' code.  The other part of
        // this hack switches the charCodes in this.insertChar!
        var hack = this._keyhacks[event.keyCode];
        if (typeof hack != "undefined") {
            if (event.type == "keydown") {
                this._ignore_keypress = true;
                event.type = "keypress";
            } else if (this._ignore_keypress && event.type == "keypress"
                    && event.keyCode == hack[1]) {
                delete this._ignore_keypress;
                return;
            }
        }

        if (event.ctrlKey) {
            switch (event.which) {
                case 90: // Z-key, for undo/redo
                    console.log("Undo for line editor");
                    event.shiftKey
                        ? this._undostack.redo()
                        : this._undostack.undo();
                    event.preventDefault();
                    return true;
                default:
            }
            return false;
        }

        switch (event.keyCode) {
            case KC_LEFT:
            case KC_RIGHT:
            case KC_UP:
            case KC_DOWN:
            case KC_HOME:
            case KC_END:
                this._keyNav(event);
                break;
            case KC_ESCAPE: // abandon changes
                this.finishEditing(this._inittext);
                break;
            case KC_RETURN: // accept changes
                this.finishEditing();
                break;
            case KC_CAPSLOCK:   // produces funny chars on Mozilla
                break;
            case KC_DELETE:
            case KC_BACKSPACE: // delete or backspace
                this.deleteChar(event.keyCode == KC_BACKSPACE);
                break;
            case KC_TAB: // finish and go to next
                this.finishEditing();
                event.shiftKey
                    ? this.trigger("onEditPrevElement")                    
                    : this.trigger("onEditNextElement");
                break;
            default:
                // char handlers - only use keypress for this
                if (event.type == "keydown")
                    return false;
                this.insertChar(event);
                event.preventDefault();
        }
        return true;
    },

    _initialiseCursor: function(clickevent) {
        // find the first letter in the series (ignore spaces)
        this._c = $(this._e).find("span").filter(function(index) {
            return $(this).text() != " ";
        }).get(0);
        $(this._cursor).css("height", $(this._c).height());
        this.positionCursorTo(this._c);
        $("body").append(this._cursor);
        this.blinkCursor(true);
    },


    _keyNav: function(event) {
        // break command compressions so further deletes/inserts
        // are undone/redone discretely
        this._undostack.breakCompression();

        // either deselect all, or set the start of a selection
        if (event.shiftKey) {
            if (!this._selectstart) {
                this._selectstart = this._c;
            }
        } else {
            this.deselectAll();
        }

        switch (event.keyCode) {
            case KC_LEFT:
                this.moveCursorLeft();
                break;
            case KC_RIGHT:
                this.moveCursorRight();
                break;
            case KC_HOME:
                this.moveCursorToStart();
                break;
            case KC_END:
                this.moveCursorToEnd();
                break;
            default:
        }
        if (event.shiftKey) {
            this.updateSelection(this._selectstart, this._c);
        }
    },


    _charClicked: function(event) {
        console.log("Char clicked: " + $(event.target).text());
        var elem = event.target;
        var offset = $(elem).offset();
        var mid = $(elem).width() / 2;
        var atend = $(elem).next().length == 0;

        // if we've clicked on the first char, position the
        // cursor, set the start marker
        if (!elem.previousElementSibling) {
            this.setCurrentChar(elem);
            return;
        }

        // if we click on latter half of the last element
        if ($(elem).next("span").length == 0 && event.pageX > (offset.left + mid)) {
            this.setCurrentChar(this._endmarker);
            return;
        }

        // otherwise, we're in the middle somewhere
        if (event.pageX >= (offset.left + mid))
            elem = elem.nextElementSibling;
        this.setCurrentChar(elem);
    },

    // get the top and left position of an element
    // looking, if necessary, at it's sibling's
    // position.  This is for when breaking elements
    // report erroneous positions
    _elementPos: function(elem) {
        var offset = $(elem).offset();
        var mintop = $(elem).parent().offset().top;
        if ($(elem).text() != " " || ($.browser.webkit && offset.top >= mintop)) {
            return {top: offset.top, left: offset.left};
        }
        // if not, find the nearest a sibling either side
        // that has position
        if (elem.previousElementSibling) {
            var back = 0;
            var prev = elem.previousElementSibling;
            while (prev) {
                back++;
                if ($(prev).text() != " ") {
                    break;
                }
                prev = prev.previousElementSibling;
            }
            var poffset = $(prev).offset();
            if (poffset.top >= mintop) {
                console.log("Got pos off previous: '" + $(prev).text() + "'");
                return {top: poffset.top, left: poffset.left + (back * $(prev).width())};
            }
        }
        if (elem.nextElementSibling) {
            var back = 0;
            var next = elem.nextElementSibling;
            while (next) {
                back++;
                if ($(next).text() != " ") {
                    break;
                }
                next = next.nextElementSibling;
            }
            var poffset = $(next).offset();
            if (poffset.top >= mintop) {
                console.log("Got pos off next: '" + $(next).text() + "'");
                return {top: poffset.top, left: poffset.left};
            }
        }
        // fall back on the parent's top/left
        var parentoffset = $(elem).parent().offset();
        if (parentoffset.top >= mintop) {
            return {top: parentoffset.top, left: parentoffset.left};
        }
        console.log("Failed to get top & left for element: " + $(elem));
        throw "Unable to get usable position for elem: "
            + $(elem) + " (" + $(elem).text() + ")";
    },

    // ensure that is the last char in the line is a space
    // that it's a non-breaking one.  Otherwise ensure that
    // all spaces are breaking entities.
    _mungeSpaces: function(event) {
        var self = this;
        if (this._endmarker.previousElementSibling) {
            var pes = this._endmarker.previousElementSibling;
            if ($(pes).text() == " ") {
                $(pes).text("\u00a0");
            }
        }
        $(this._endmarker).prevAll().filter(function(i) {
            if ($(this).text() == "\u00a0") {
                if ($(this).next().text().match(/\S/)
                        && $(this).prev().text() != " ") {
                    return true;
                }
            }
        }).each(function(i, elem) {
            $(elem).text(" ");
        });
        // replace a first breaking space with a hard breaking one
        var firstelem = $(this._e).children().first();
        if (firstelem.length && firstelem.text() == " ") {
            firstelem.text("\u00a0");
        }
    },


    _selectCurrentWord: function(event) {
        // this is TERRIBLE!  Whatever, too late, will
        // fix it in the cold light of day.
        if (!event.shiftDown)
            this.deselectAll();
        var startchar = this._c;
        while (startchar.previousElementSibling
                && startchar.previousElementSibling.textContent.match(/^\w$/)) {
            startchar = startchar.previousElementSibling;
        }
        var endchar = this._c;
        while (endchar && endchar != this._endmarker
                && endchar.textContent.match(/^\w$/)) {
            endchar = endchar.nextElementSibling;
        }
        this.updateSelection(startchar, endchar);
    },


    _selectCharUnderPoint: function(event) {
        if (!event)
            return;
        // find the 'new' span element that would've
        // been under the mouse when clicked
        for (var i = 0; i < $(this._e).children("span").length; i++) {
            var elem = $(this._e.children[i]);
            var elemoffset = elem.offset();
            if (!elemoffset)
                continue;
            if (event.pageX < elemoffset.left)
                continue;
            if (event.pageX > elemoffset.left + elem.width())
                continue;
            if (event.pageY < elemoffset.top)
                continue;
            if (event.pageY > elemoffset.top + elem.height())
                continue;
            this._c = elem.get(0);
            if (event.pageX > (elemoffset.left + (elem.width() / 2)))
                this._c = elem.next().get(0);
            break;
        }
        if (!this._selectstart) {
            this._selectstart = this._c;
        } else {
            this.updateSelection(this._selectstart, this._c);
        }
        this.positionCursorTo(this._c);
    },
});