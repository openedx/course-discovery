$(function() {
    'use strict';

    var keys = {
        'left':     37,
        'right':    39,
        'down':     40,
        'up':       38
    };
    
    var Tabs = {
        
        init: function() {
            Tabs.resetTabs();

            var $studioTab = $('#tab-studio'),
                studioCount = $studioTab.data('studioCount'),
                startTab = studioCount > 0 ? $studioTab : $('.tabs .tab').first(),
                startPanel = $(startTab).attr('aria-controls');

            Tabs.activateTab(startTab, startPanel);

            Tabs.keyListener();
            Tabs.clickListener();
        },
        
        resetTabs: function() {
            $('.tabs .tab').each(function(i, el) {
                var tab = $(el);
                
                $(tab).removeClass('is-active').attr({
                    'aria-selected': 'false',
                    'aria-expanded': 'false',
                    'tabindex': '-1'
                });
            });
            
            Tabs.resetTabPanels();
        },
        
        resetTabPanels: function() {
            $('.tab-panel').each(function(i, el) {
                var panel = $(el);
                
                $(panel)
                    .removeClass('is-active')
                    .attr({
                        'tabindex': '-1',
                        'aria-hidden': 'true'
                    });
            });
        },

        keyListener: function() {
            $('.tabs .tab').on('keydown', function(e) {
                var key = e.which,
                    focused = $(e.currentTarget),
                    index = $(e.currentTarget).parent().find('.tab').index(focused),
                    total = $(e.currentTarget).parent().find('.tab').length - 1,
                    panel = $(focused).attr('aria-controls');
                
                switch (key) {
                    case keys.left:
                    case keys.up:
                        Tabs.previousTab(focused, index, total, e);
                        break;
                        
                    case keys.right:
                    case keys.down:
                        Tabs.nextTab(focused, index, total, e);
                        break;
                        
                    default:
                        return true;
                }
            });
        },
        
        clickListener: function() {
            $('.tabs .tab').on('click', function(e) {
                var tab = $(e.currentTarget),
                    panel = $(tab).attr('aria-controls');

                Tabs.resetTabs();
                Tabs.activateTab(tab, panel);
            });
        },
        
        previousTab: function(focused, index, total, event) {            
            var tab, panel;

            if (event.altKey || event.shiftKey) {
                return true;
            }

            if (index === 0) {
                tab = $(focused).parent().find('.tab').last();
                panel = $(tab).attr('aria-controls');
                
            } else {
                tab = $(focused).parent().find('.tab:eq(' + index + ')').prev();
                panel = $(tab).attr('aria-controls');
            }
            
            tab.focus();
            Tabs.activateTab(tab, panel);

            return false;
        },
        
        nextTab: function(focused, index, total, event) {
            var tab, panel;

            if (event.altKey || event.shiftKey) {
                return true;
            }

            if (index === total) {
                tab = $(focused).parent().find('.tab').first();
                panel = $(tab).attr('aria-controls');
                
            } else {
                tab = $(focused).parent().find('.tab:eq(' + index + ')').next();
                panel = $(tab).attr('aria-controls');
            }
            
            tab.focus();
            Tabs.activateTab(tab, panel);
            
            return false;
        },
        
        activateTab: function(tab, panel) {
            Tabs.resetTabs();
            Tabs.activateTabPanel(panel);
            
            $(tab)
                .addClass('is-active')
                .attr({
                    'aria-selected': 'true',
                    'aria-expanded': 'true',
                    'tabindex': '0'
                });
        },
        
        activateTabPanel: function(panel) {
            Tabs.resetTabPanels();
            $('#' + panel)
                .addClass('is-active')
                .attr('aria-hidden', 'false');
        }
    };
    
    Tabs.init();
});
