/* jshint asi:true, expr:true */
({
    mainConfigFile: 'course_discovery/static/js/config.js',
    baseUrl: 'course_discovery/static',
    dir: 'course_discovery/static/build',
    removeCombined: true,
    findNestedDependencies: true,

    // Disable all optimization. django-compressor will handle that for us.
    optimizeCss: false,
    optimize: 'none',
    normalizeDirDefines: 'all',
    skipDirOptimize: true,

    preserveLicenseComments: true,
    modules: [
        {
            name: 'js/config'
        },
    ]
})
