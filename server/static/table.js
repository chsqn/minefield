
/* jshint undef: true */
/* global $ */
/* global Tiles */

// data: {tiles, dora_ind, east, you}
function Table($elt, data, complete) {
    var self = {
        $elt: $elt,
        find: function(sel) { return self.$elt.find(sel); },
        state: null
    };

    self.init = function() {
        self.$elt.html($('#templates > .table').html());

        Tiles.add(self.find('.tiles'), data.tiles);
        Tiles.sort(self.find('.tiles'));

        var $wind = $("<img/>");
        if (data.east == data.you)
            $wind.attr('src', 'tiles/E.svg').attr('title', 'East');
        else
            $wind.attr('src', 'tiles/W.svg').attr('title', 'West');
        self.find(".east-display").append($wind);

        self.find(".dora-display").append(Tiles.create(data.dora_ind));

        self.init_events();
    };

    self.init_events = function() {
        function update_submit() {
            self.find('.submit-hand').prop(
                'disabled',
                self.find('.hand > .tile').length < 13);
        }

        update_submit();

        self.$elt.on('click', '.tiles .tile', function() {
            if (self.state == 'select_hand') {
                if (self.find('.hand > .tile').length >= 13)
                    return;

                self.add_tile_to_hand($(this));
                update_submit();
            } else if (self.state == 'discard') {
                self.discard_complete($(this));
            }
        });

        self.$elt.on('click', '.hand .tile', function() {
            if (self.state == 'select_hand') {
                self.remove_tile_from_hand($(this));
                update_submit();
            }
        });

        self.$elt.on('click', '.submit-hand', function() {
            if (self.state == 'select_hand') {
                self.select_hand_complete();
            }
        });
    };

    self.select_hand = function(handler) {
        self.state = 'select_hand';
        self.find('.submit-hand').show();
        self.find('.tiles').addClass('tiles-clickable');
        self.find('.hand').addClass('outlined tiles-clickable');
        self.on_select_hand = handler;
    };

    self.select_hand_complete = function() {
        self.state = null;
        self.find('.submit-hand').hide();
        self.find('.tiles').removeClass('tiles-clickable');
        self.find('.hand').removeClass('outlined tiles-clickable');
        self.on_select_hand(Tiles.list(self.find('.hand')));
    };

    self.discard = function(handler) {
        self.state = 'discard';
        self.find('.tiles').addClass('tiles-clickable');
        self.on_discard = handler;
    };

    self.discard_complete = function($tile) {
        self.state = null;
        var tile_code = $tile.data('tile');
        $tile.replaceWith(Tiles.create_placeholder($tile));
        $tile.appendTo(self.find('.discards'));
        self.find('.tiles').removeClass('tiles-clickable');
        self.on_discard(tile_code);
    };

    self.opponent_discard = function(tile_code) {
        self.find('.opponent-discards').append(Tiles.create(tile_code));
    };

    self.add_tile_to_hand = function($tile) {
        $tile.replaceWith(Tiles.create_placeholder($tile));
        $tile.appendTo(self.find('.hand'));
        Tiles.sort(self.find('.hand'));
    };

    self.remove_tile_from_hand = function($tile) {
        var tile_code = $tile.data('tile');
        $tile.detach();
        $tile.replaceAll(self.find('.tiles .tile-placeholder[data-tile='+tile_code+']').first());
    };

    self.init();
    return self;
}
