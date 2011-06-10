//
// Class representing a plug on a node
//

OCRJS.Nodetree.BasePlug = OCRJS.OcrBase.extend({
    constructor: function(node, name) {
        this.base();

        this.node = node;
        this.name = name;
        this._pw = 30;
        this._ph = 20;

        this._listeners = {
            wired: [],
            attachCable: [],
            moved: [],
            hoverIn: [],
            hoverOut: [],
            rightClicked: [],
        };        
    },

    group: function() {
        return this._group;
    },        

    draw: function(svg, parent, x, y) {
        var self = this;
        self.svg = svg;
        self._group = svg.group(parent, self.name);                
        self._rect = svg.rect(parent, 
                x - (this._pw / 2), y - (this._ph / 2), this._pw, this._ph, 5, 5, {
            fill: this._gradient,
            stroke: "#BBB",
            strokeWidth: 1,
        });                        
        this.setupEvents();
    },

    wouldAccept: function(other) {
        if (other.type == this.type)
            return false;
        if (other == this)
            return false;
        if (other.node == this.node)
            return false;
        return true;
    },              

    setAcceptingState: function() {
        this.svg.change(this._rect, {fill: "url(#PlugAccept)"});
    },

    setRejectingState: function() {
        this.svg.change(this._rect, {fill: "url(#PlugReject)"});
    },

    setDefaultState: function() {
        this.svg.change(this._rect, {fill: this._gradient});
    },                         

    setDraggingState: function() {
        this._dragging = true;                          
        this.svg.change(this._rect, {fill: "url(#PlugDragging)"});
    },                         

    setupEvents: function() {
        var self = this;

        $(self._rect).noContext().rightClick(function(event) {
            self.callListeners("rightClicked", event);
        });            

        $(self._rect).bind("click.attachcable", function(event) {
            self.callListeners("attachCable", self);
            event.stopPropagation();
            event.preventDefault();
        }).hover(function(event) {
            self.callListeners("hoverIn", self);
            //self.setAcceptingState(); 
        }, function(event) {
            self.callListeners("hoverOut", self);
            self.setDefaultState();    
        });
    },

    centre: function() {
        //return this.centrePointOfCircle(this._circle);
        return {
            x: parseInt($(this._rect).attr("x")) + this._pw / 2,
            y: parseInt($(this._rect).attr("y")) + this._ph / 2,
        };
    },

    isOutput: function() {
        return this.type == "output";
    },

    isInput: function() {
        return this.type == "input";
    },        
});


OCRJS.Nodetree.InPlug = OCRJS.Nodetree.BasePlug.extend({
    constructor: function(node, name) {
        this.base(node, name);
        this.type = "input";
        this._gradient = "url(#InPlugGradient)";
        this._cable = null;
    },

    toString: function() {
        return "<InPlug: " + this.name + ">";
    },                  

    attach: function(cable) {
        if (this._cable)
            this._cable.remove();
        this._cable = cable;
    },

    detach: function() {
        if (this._cable)
            this._cable.remove();
        this._cable = null;
    },                
    
    cable: function() {
        return this._cable;
    },
    
    isAttached: function() {
        return Boolean(this._cable);
    },        
});

OCRJS.Nodetree.OutPlug = OCRJS.Nodetree.BasePlug.extend({
    constructor: function(node, name) {
        this.base(node, name);
        this.type = "output";
        this._gradient = "url(#OutPlugGradient)";
    },

    toString: function() {
        return "<OutPlug: " + this.name + ">";
    },                  
});
