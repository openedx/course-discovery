'use strict';

var gulp = require('gulp'),
    jscs = require('gulp-jscs'),
    path = require('path'),
    paths = {
        spec: [
            'course_discovery/static/js/**/*.js',
            'course_discovery/static/templates/**/*.js'
        ],
        lint: [
            'build.js',
            'gulpfile.js',
            'course_discovery/static/js/**/*.js',
            'course_discovery/static/js/test/**/*.js'
        ]
    };

/**
 * Runs the JavaScript Code Style (JSCS) linter.
 *
 * http://jscs.info/
 */
gulp.task('jscs', function () {
    return gulp.src(paths.lint)
        .pipe(jscs());
});

/**
 * Monitors the source and test files, running tests
 * and linters when changes detected.
 */
gulp.task('watch', function () {
    gulp.watch(paths.spec, ['jscs']);
});
