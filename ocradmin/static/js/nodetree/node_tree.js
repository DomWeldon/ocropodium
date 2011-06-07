//
// Fancy pants parameter tree.
//

var OCRJS = OCRJS || {}
var NT = OCRJS.Nodetree;
var SvgHelper = SvgHelper || new OCRJS.Nodetree.SvgHelper();

OCRJS.Nodetree.NodeTree = OCRJS.Nodetree.NodeList.extend({
    constructor: function(parent, options) {
        this.base(parent, options);

        this.parent = parent;
        this.svg = null;
        this._dragcable = null;
        this._nodes = [];
        this._usednames = {};
        this._nodedata = {};
        this._nodetypes = {};
        this._menutemplate = $.template($("#nodeMenuTmpl"));
    },


    init: function() {
        this.queryNodeTypes();
    },

    group: function() {
        return this._group;
    },        

    setupNodeListeners: function(node) {
        var self = this;                            
        node.addListeners({
            toggleIgnored: function(ig) {
                self.scriptChange();
            },
            toggleFocussed: function(foc) {
                $.each(self._usednames, function(name, other) {
                    if (node.name != name)
                        other.setFocussed(false);
                });
                self.buildParams(node);
                self.scriptChange();
            },
            toggleViewing: function(view) {
                $.each(self._usednames, function(name, other) {
                    if (node.name != other.name)
                        other.setViewing(false);
                });
                self.scriptChange();
            },
            deleteInitiated: function() {
                // when we're about to delete a node, clean
                // up its cables
                // check if we've got an input                
                console.log("Delete initiated:", node.name);
                var outplug = node.output();
                var referencees = self.attachedInputs(outplug);
                for (var i in referencees)
                    referencees[i].detach();                
                var input = node.input(0);
                if (!(input && input.isAttached()))
                    return;
                var srcplug = input.cable().start;
                for (var i in referencees) {
                    self.connectPlugs(srcplug, referencees[i]);

                }
            },                                 
            deleted: function() {
                console.log("Deleted node:", node.name);
                self.scriptChange();
            },
            inputAttached: function(plug) {
                console.log("Attached input to", node.name, plug.name);
                self.handlePlug(plug);
            },                               
            outputAttached: function(plug) {
                console.log("Attached output to", node.name, plug.name);
                self.handlePlug(plug);
            },
            plugHoverIn: function(plug) {
                self.handlePlugHover(plug);
            },            
        });
    },

    removeDragCable: function() {
        if (this._dragcable) {
            this._dragcable.start.setDefaultState();
            this._dragcable.remove();
            this._dragcable = null;
        }
        $(document).unbind(".dragcable").unbind(".dropcable");
    },                        

    handlePlug: function(plug) {
        var self = this;
        if (!self._dragcable && plug.isInput() && plug.isAttached()) {
            plug.detach();
            self.startCableDrag(plug);
        } else if (!self._dragcable) {
            self.startCableDrag(plug);
        } else {
            if (self._dragcable.start.wouldAccept(plug)) {
                if (plug.isInput() && plug.isAttached())
                    plug.detach();
                if (self._dragcable.start.isInput())
                    self.connectPlugs(plug, self._dragcable.start);
                else
                    self.connectPlugs(self._dragcable.start, plug);
            }
            self.removeDragCable();    
        }            
    },

    handlePlugHover: function(plug) {
        var self = this;
        if (self._dragcable) {
            var other = self._dragcable.start;
            if (plug.wouldAccept(other)) {
                plug.setAcceptingState();
            } else {
                plug.setRejectingState();
            }
        } else {
            plug.setAcceptingState();
        }            
    },                         

    startCableDrag: function(plug) {
        var self = this;                        
        var cable = new NT.DragCable(plug);
        var point = SvgHelper.denorm(plug.centre(), plug.group(), self.group());
        cable.draw(self.svg, self._cablegroup, point, point);
        self._dragcable = cable;
        plug.setDraggingState();
        $(document).bind("mousemove.dragcable", function(event) {
            var npoint = SvgHelper.denorm(plug.centre(), plug.group(), self.group());
            var nmp = SvgHelper.norm(
                SvgHelper.mouseCoord(self.parent, event), cable.group(), null);
            cable.update(npoint, SvgHelper.divPoints(nmp, 
                    SvgHelper.getScale(self.group())));
        }); 
        $(self.group()).bind("click.dropcable", function(event) {
            self.removeDragCable();
        });
    },

    connectPlugs: function(src, dst) {
        var self = this;                        
        var cable = new NT.Cable(src, dst);
        var p1 = SvgHelper.denorm(src.centre(), src.group(), this.group());
        var p2 = SvgHelper.denorm(dst.centre(), dst.group(), this.group());
        src.addListener("moved", function() {
            var m1 = SvgHelper.denorm(src.centre(), src.group(), self.group());
            var m2 = SvgHelper.denorm(dst.centre(), dst.group(), self.group());
            cable.update(m1, m2);            
        });
        dst.addListener("moved", function() {
            var m1 = SvgHelper.denorm(src.centre(), src.group(), self.group());
            var m2 = SvgHelper.denorm(dst.centre(), dst.group(), self.group());
            cable.update(m1, m2);            
        });
        cable.draw(self.svg, self._cablegroup, p1, p2);
    },

    attachedInputs: function(outplug) {
        // since output plugs have no knowledge of what's
        // attached to them we have to search all the nodes
        // to find any that reference a given output.                        
        var inplugs = [];
        $.each(this._nodes, function(ni, node) {
            $.each(node.inputs(), function(i, input) {
                if (input.isAttached() && input.cable().start == outplug)
                    inplugs.push(input);
            });                
        });            
        return inplugs;
    },                        

    setupEvents: function() {
        var self = this;                     
        $(self._group).noContext().rightClick(function(event) {
            self._menu.show();
            var maxx = $(self.parent).offset().left + $(self.parent).width();
            var left = event.clientX;
            if (event.clientX + self._menu.outerWidth() > maxx)
                left = maxx - (self._menu.outerWidth() + 20);
            self._menu.css({
                top: event.clientY,
                left: left,    
            });
        });
        $(self._group).click(function(event) {
           self._menu.hide();
        });

        $("#optionsform").submit(function(event) {
            self.runScript();
            event.preventDefault();
            event.stopPropagation();
        });

        $(".node.floating").live("click", function(event) {
            $(this).removeClass("floating");
            $(document).unbind("mousemove.dropnode");
        });

        function nodeCmd(event) {
            if (event.which == 61 || event.which == 45) {                    
                if (event.which == 61)
                    self.scaleContainer(1.5);                
                else
                    self.scaleContainer(0.75);
            }
        }
        $(self.parent).bind("mousewheel.zoomcanvas", function(event) {
            if (event.wheelDelta < 0)
                self.scaleContainer(0.9);
            else
                self.scaleContainer(1.1);
        });
        $(this._group).bind("mousedown", function(event) {
            if (event.button == 1 || event.button == 0 && event.shiftKey) {
                self.panContainer(event, this);
                event.preventDefault();
                event.stopPropagation();
            }
        });

        $(document).bind("keydown.nodecmd", function(event) {
            //nodeCmd(event);
            if (event.which == KC_DELETE)
                self.deleteSelected();
        });
        //$(document).bind("keypress.nodecmd", nodeCmd);
        $(self.parent).bind("mouseenter", function(mvevent) {
            $(document).bind("keypress.nodecmd", function(event) {
                nodeCmd(event);
            });
        });        
        $(self.parent).bind("mouseleave", function(mvevent) {
            $(document).unbind("keypress.nodecmd");
            $(document).unbind("mousewheel.zoomcanvas");
        });
    },         

    setupMenuEvents: function() {
        var self = this;                         
        self._menu.find("li").hover(function(event) {
            $(this).addClass("selected");
        }, function(event) {
            $(this).removeClass("selected");
        });
        self._menu.find("li.topmenu").hoverIntent(
            function(event) {
                var pos = $(this).position();
                var left = pos.left + $(this).outerWidth() - 5;
                var sub = $(this).find("ul");
                sub.show();
                sub.css({left: left, top: $(this).position().top})
                var span = $(this).offset().left + $(this).outerWidth() + sub.outerWidth();
                var outer = $(self.parent).offset().left + $(self.parent).width();
                if (span > outer) {
                    sub.css("left", pos.left - sub.outerWidth());
                }
            },
            function(event) {
                $(this).find("ul").delay(1000).hide();            
            }
        );

        self._menu.find(".topmenu").find("li").click(function(event) {
            self.createNode($(this).data("name"), 
                    SvgHelper.mouseCoord(self.parent, event));
            self._menu.hide();
            event.stopPropagation();
            event.preventDefault();
        });
    },

    buildNodeMenu: function() {
        var self = this;
        self._menu = $.tmpl(this._menutemplate, {
            stages: self._nodedata,
        }).hide();
        $(self.parent).append(self._menu);
        self.setupMenuEvents();
    },    

    populateCanvas: function() {
        var self = this;                        
        $(this.parent).svg({                    
            onLoad: function(svg) {
                self.svg = svg;
                self.drawTree();
                self.loadState();
                self.setupEvents();
                self.buildNodeMenu();
            },
        });
    },

    loadScript: function(script) {
        var self = this;
        if (script.length < 1)
            return;
        var havemeta = false;
        $.each(script, function(i, node) {
            var typedata = self._nodetypes[node.type];
            var newnode = self.addNode(node.name, typedata);
            newnode.setIgnored(node.ignored);  
            $.each(node.params, function(i, p) {
                newnode.parameters[i].value = p[1];
            });
            if (node.__meta) {
                havemeta = true;
                newnode.moveTo(node.__meta.x, node.__meta.y);
                newnode.setViewing(node.__meta.viewing);
                newnode.setFocussed(node.__meta.focussed);
            }
        });
        this.connectNodes(script);
        if (script.length > 0)
            if (!havemeta)
                this.layoutNodes(script);
        this.scriptChange();
    },                    

    addNode: function(name, typedata) {
        var id = $.map(this._usednames, function(){return true;}).length;
        var node = new NT.TreeNode(name, typedata, id);
        this.setupNodeListeners(node);
        this._usednames[name] = node;
        this._nodes.push(node);
        node.draw(this.svg, this._group, 0, 0);
        return node;
    },                 

    createNode: function(type, atpoint) {
        var self = this;                    
        var name = self.newNodeName(type);
        var typedata = self._nodetypes[type];
        var nodeobj = self.addNode(name, typedata);
        var point = SvgHelper.norm(atpoint, self.group());
        nodeobj.moveTo(atpoint.x - 75, atpoint.y - 25);
        $(document).bind("keydown.dropnode", function(event) {
            if (event.which == KC_ESCAPE)
                nodeobj.remove();
        });
        $(self._group).bind("mousemove.dropnode", function(event) {
            var point = SvgHelper.norm(SvgHelper.mouseCoord(self.parent, event), self.group());
            nodeobj.moveTo(point.x - 75, point.y - 25);
            $(document).add($(nodeobj.group()).find("*")).bind("click.dropnode", function(e) {
                $(self._group).unbind(".dropnode");
                $(document).add($(nodeobj.group()).find("*")).unbind(".dropnode");
            });
        });            
    },

    deleteNode: function(node) {
        var i = this._nodes.indexOf(node);
        console.assert(i > -1, "Node", node.name, "not found in self._nodes");
        delete this._usednames[node.name];
        this._nodes.splice(i, 1);
        node.removeNode();
    },                    

    deleteSelected: function() {
        for (var i in this._nodes) {
            if (this._nodes[i].isFocussed()) {
                this.deleteNode(this._nodes[i]);
            }                
        }            
    },                        

    buildScript: function() {
        return $.map(this._nodes, function(n) {
            return n.serialize();
        });
    },                     

    drawTree: function() {
        var self = this,
            svg = this.svg;

        this._group = svg.group(null, "canvas");
        this.defineGradients();
        self._cablegroup = svg.group(this._group, "cables");
        var container = svg.rect(this._group, 0, 0, svg._width(), svg._height(), {
            fill: "transparent",
            fillOpacity: 0,
            stroke: "transparent",    
        });
    },

    connectNodes: function(treenodes) {
        var self = this;                      
        $.each(treenodes, function(ni, node) {
            $.each(node.inputs, function(i, input) {
                var n1 = self._usednames[input];
                var n2 = self._usednames[node.name];
                self.connectPlugs(n1.output(), n2.input(i));
            });
        });    
    },                      

    layoutNodes: function(script) {
        var self = this;                
        $.ajax({            
            url: "/plugins/layout_graph",
            type: "POST",
            data: {script: JSON.stringify(script)},
            success: function(data) {
                $.each(data, function(node, value) {
                    self._usednames[node].moveTo(value[0], 
                            (self.svg._height() - value[1]) - 100);
                });
            },
            error: OCRJS.ajaxErrorHandler,
        });
    },                

    panContainer: function(event, element) {
        var dragstart = {
            x: event.pageX,
            y: event.pageY,
        };
        var self = this;
        var trans = SvgHelper.getTranslate(element);
        var scale = SvgHelper.getScale(element);
        $(document).bind("mousemove.dragelem", function(moveevent) {
            SvgHelper.updateTranslate(element, 
                trans.x + ((moveevent.pageX - dragstart.x) / scale.x),
                trans.y + ((moveevent.pageY - dragstart.y) / scale.y));
        });
        $(document).bind("mouseup.unloaddrag", function() {
            $(this).unbind("mousemove.dragelem");
            $(this).unbind("mouseup.unloaddrag");
            var enlarge = $(element).children("rect");
            var trans = SvgHelper.getTranslate(element);
            if (trans.x > 0) {
                enlarge.attr("x", parseInt(enlarge.attr("x")) - trans.x);
                enlarge.attr("width", parseInt(enlarge.attr("width")) + trans.x);
            } else
                enlarge.attr("width", parseInt(enlarge.attr("width")) - trans.x);
            if (trans.y > 0) {
                enlarge.attr("y", parseInt(enlarge.attr("y")) - trans.y);
                enlarge.attr("height", parseInt(enlarge.attr("height")) + trans.y);
            } else
                enlarge.attr("height", parseInt(enlarge.attr("height")) - trans.y);
        });
    },

    scaleContainer: function(by) {
        var scale = SvgHelper.getScale(this.group());
        var cx = scale.x, cy = scale.y;
        cx *= by, cy *= by;
        SvgHelper.updateScale(this.group(), cx, cy);
    },

    defineGradients: function() {                         
        var defs = this.svg.defs(this._group);
        this.svg.linearGradient(defs, "NodeGradient", 
            [["0%", "#f8f8f8"], ["100%", "#ebebeb"]], "0%", "0%", "0%", "100%");
        this.svg.linearGradient(defs, "FocusGradient", 
            [["0%", "#f9fcf7"], ["100%", "#f5f9f0"]], "0%", "0%", "0%", "100%");
        this.svg.linearGradient(defs, "ErrorGradient", 
            [["0%", "#fdedef"], ["100%", "#f9d9dc"]], "0%", "0%", "0%", "100%");
        this.svg.linearGradient(defs, "ViewingGradient", 
            [["0%", "#a9cae5"], ["100%", "#6ea2cc"]], "0%", "0%", "0%", "100%");
        this.svg.linearGradient(defs, "IgnoreGradient", 
            [["0%", "#ffffcf"], ["100%", "#ffffad"]], "0%", "0%", "0%", "100%");
        this.svg.linearGradient(defs, "InPlugGradient", 
            [["0%", "#d8d8d8"], ["100%", "#dbdbdb"]], "0%", "0%", "0%", "100%");
        this.svg.linearGradient(defs, "OutPlugGradient", 
            [["0%", "#dbdbdb"], ["100%", "#d8d8d8"]], "0%", "0%", "0%", "100%");
        this.svg.linearGradient(defs, "PlugAccept", 
            [["0%", "#dbf0ca"], ["100%", "#d3e7c3"]], "0%", "0%", "0%", "100%");
        this.svg.linearGradient(defs, "PlugReject", 
            [["0%", "#fdedef"], ["100%", "#f9d9dc"]], "0%", "0%", "0%", "100%");
        this.svg.linearGradient(defs, "PlugDragging", 
            [["0%", "#a9cae5"], ["100%", "#6ea2cc"]], "0%", "0%", "0%", "100%");
    },
});
