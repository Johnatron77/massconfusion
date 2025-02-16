window.addEventListener("load", function() {
    (function ($) {
        $('<li id="show-filters"><a href="#">Show filters</a></li>').appendTo('ul.object-tools');
        $('<li id="hide-filters"><a href="#">Hide filters</a></li>').appendTo('ul.object-tools');

        $('#hide-filters').hide();
        $('#changelist-filter').hide();

        $('#show-filters').click(function () {
            $('#changelist-filter').show('fast');
            $('#show-filters').hide();
            $('#hide-filters').show();
        });

        $('#hide-filters').click(function () {
            $('#changelist-filter').hide('fast');
            $('#show-filters').show();
            $('#hide-filters').hide();
        });
    })(django.jQuery);
});