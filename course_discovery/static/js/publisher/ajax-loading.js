(function($){
    var config = {};

    $.loadingSpinner = function (options) {

        var opts = $.extend(
            $.loadingSpinner.default,
            options
        );

        config = opts;
        init(opts);

        var selector = '#' + opts.id;

        $(document).on('ajaxStart', function(){
            if (config.ajax) {
                $(selector).show();
            }
        });

        $(document).on('ajaxComplete', function(){
            setTimeout(function(){
                $(selector).hide();
            }, opts.minTime);
        });

        return $.loadingSpinner;
    };

    $.loadingSpinner.open = function (time) {
        var selector = '#' + config.id;
        $(selector).show();
        if (time) {
            setTimeout(function(){
                $(selector).hide();
            }, parseInt(time));
        }
    };

    $.loadingSpinner.close = function () {
        var selector = '#' + config.id;
        $(selector).hide();
    };

    $.loadingSpinner.ajax = function (isListen) {
        config.ajax = isListen;
    };

    $.loadingSpinner.default = {
        ajax       : true,
        //wrap div
        id         : 'ajaxLoading',
        zIndex     : '10000',
        background : 'rgba(0, 0, 0, 0.7)',
        minTime    : 200,
        width      : '100%',
        height     : '100%',

        //loading img/gif
        imgPath    : '/static/images/ajax-loading.svg',
        imgWidth   : '65px',
        imgHeight  : '65px'
    };

    function init (opts) {
        //wrap div style
        var wrapCss = 'display: none;position: fixed;top: 0;bottom: 0;left: 0;right: 0;margin: auto;text-align: center;vertical-align: middle;';
        var cssArray = [
            'width:' + opts.width,
            'height:' + opts.height,
            'z-index:' + opts.zIndex,
            'background:' + opts.background
        ];
        wrapCss += cssArray.join(';');

        //img style
        var imgCss = 'top: 0;bottom: 0;left: 0;right: 0;margin: auto;position: absolute;';
        cssArray = [
            'width:' + opts.imgWidth,
            'height:' + opts.imgWidth
        ];
        imgCss += cssArray.join(';');

        var html = '<div id="' + opts.id + '" style="' + wrapCss + '">'
                  +'<img src="' + opts.imgPath + '" style="' + imgCss + '">';

        $(document).find('body').append(html);
    }

})(window.jQuery||window.Zepto);
