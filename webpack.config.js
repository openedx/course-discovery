var BundleTracker = require('webpack-bundle-tracker'),
    MiniCssExtractPlugin = require('mini-css-extract-plugin'),
    path = require('path'),
    webpack = require('webpack'),
    loaders = [
        MiniCssExtractPlugin.loader,
        'css-loader',
        {
            loader: 'sass-loader',
            options: {
                sassOptions: {
                    includePaths: [path.resolve('./sass/')]
                }
            }
        }
    ],
    context = path.join(__dirname, 'course_discovery/static');

module.exports = {
    context: context,
    mode: 'production',
    entry: {
        'query-preview': './js/query-preview.js',
        'course-skills-admin': './js/course-skills-admin.js',
        'query-preview.style': './sass/query-preview.scss'
    },

    output: {
        path: path.join(context, './bundles/'),
        filename: '[name]-[hash].js',
        publicPath: ''
    },

    plugins: [
        new BundleTracker({filename: './webpack-stats.json'}),
        new webpack.ProvidePlugin({
            $: 'jquery',
            jQuery: 'jquery',
            'window.jQuery': 'jquery'
        }),
        new MiniCssExtractPlugin({filename: '[name]-[hash].css'})
    ],

    module: {
        rules: [
            {
                test: /\.s?css$/,
                use: loaders
            },
            {
                test: /\.woff2?$/,
                // Inline small woff files and output them below font
                use: [{
                    loader: 'url-loader',
                    options: {
                        name: 'font/[name]-[hash].[ext]',
                        limit: 5000,
                        mimetype: 'application/font-woff'
                    }
                }]
            },
            {
                test: /\.(ttf|eot|svg)$/,
                use: [{
                    loader: 'file-loader',
                    options: {
                        name: 'font/[name]-[hash].[ext]'
                    }
                }]
            },
            {
                test: require.resolve('datatables.net'),
                use: 'imports-loader?define=>false'
            },
            {
                test: require.resolve('datatables.net-bs'),
                use: 'imports-loader?define=>false'
            }
        ]
    },
    resolve: {
        modules: ['node_modules'],
        extensions: ['.css', '.js', '.scss']
    }
};
