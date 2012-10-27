#!/usr/bin/env python

from cStringIO import StringIO
import glob
import gzip
import json
import os
import shutil
import time

import pake

pake.variables['JSDOC'] = 'jsdoc'
pake.variables['PHANTOMJS'] = 'phantomjs'

EXPORTS = [path
           for path in pake.ifind('src')
           if path.endswith('.exports')
           if path != 'src/objectliterals.exports']

BRANCH = pake.output('git', 'rev-parse', '--abbrev-ref', 'HEAD').strip()

EXTERNAL_SRC = [
    'build/src/external/externs/types.js',
    'build/src/external/src/exports.js',
    'build/src/external/src/types.js']

EXAMPLES = [path
            for path in glob.glob('examples/*.html')
            if path != 'examples/example-list.html']

EXAMPLES_SRC = [path
                for path in pake.ifind('examples')
                if path.endswith('.js')
                if not path.endswith('.combined.js')
                if path != 'examples/Jugl.js'
                if path != 'examples/example-list.js']

INTERNAL_SRC = [
    'build/src/internal/src/requireall.js',
    'build/src/internal/src/types.js']

SPEC = [path
        for path in pake.ifind('test/spec')
        if path.endswith('.js')]

SRC = [path
       for path in pake.ifind('src/ol')
       if path.endswith('.js')]

PLOVR_JAR = 'bin/plovr-eba786b34df9.jar'


def report_sizes(t):
    t.info('uncompressed: %d bytes', os.stat(t.name).st_size)
    stringio = StringIO()
    gzipfile = gzip.GzipFile(t.name, 'w', 9, stringio)
    with open(t.name) as f:
        shutil.copyfileobj(f, gzipfile)
    gzipfile.close()
    t.info('  compressed: %d bytes', len(stringio.getvalue()))


pake.virtual('all', 'build-all', 'build', 'examples')


pake.virtual('precommit', 'lint', 'build-all', 'test', 'doc', 'build', 'build-examples')


pake.virtual('build', 'build/ol.css', 'build/ol.js')


@pake.target('build/ol.css', 'build/ol.js')
def build_ol_css(t):
    t.touch()


@pake.target('build/ol.js', PLOVR_JAR, SRC, EXTERNAL_SRC, 'base.json', 'build/ol.json')
def build_ol_js(t):
    t.output('java', '-jar', PLOVR_JAR, 'build', 'build/ol.json')
    report_sizes(t)


pake.virtual('build-all', 'build/ol-all.js')


@pake.target('build/ol-all.js', PLOVR_JAR, SRC, INTERNAL_SRC, 'base.json', 'build/ol-all.json')
def build_ol_all_js(t):
    t.output('java', '-jar', PLOVR_JAR, 'build', 'build/ol-all.json')


@pake.target('build/src/external/externs/types.js', 'bin/generate-exports', 'src/objectliterals.exports')
def build_src_external_externs_types_js(t):
    t.output('bin/generate-exports', '--externs', 'src/objectliterals.exports')


@pake.target('build/src/external/src/exports.js', 'bin/generate-exports', 'src/objectliterals.exports', EXPORTS)
def build_src_external_src_exports_js(t):
    t.output('bin/generate-exports', '--exports', 'src/objectliterals.exports', EXPORTS)


@pake.target('build/src/external/src/types.js', 'bin/generate-exports', 'src/objectliterals.exports')
def build_src_external_src_types_js(t):
    t.output('bin/generate-exports', '--typedef', 'src/objectliterals.exports')


@pake.target('build/src/internal/src/requireall.js', 'bin/generate-requireall', SRC)
def build_src_internal_src_requireall_js(t):
    t.output('bin/generate-requireall', '--require=goog.dom')


@pake.target('build/src/internal/src/types.js', 'bin/generate-exports', 'src/objectliterals.exports')
def build_src_internal_types_js(t):
    t.output('bin/generate-exports', '--typedef', 'src/objectliterals.exports')


pake.virtual('build-examples', 'examples', (path.replace('.html', '.combined.js') for path in EXAMPLES))


pake.virtual('examples', 'examples/example-list.js', (path.replace('.html', '.json') for path in EXAMPLES))


@pake.target('examples/example-list.js', 'bin/exampleparser.py', EXAMPLES)
def examples_examples_list_js(t):
    t.run('bin/exampleparser.py', 'examples', 'examples')


@pake.rule(r'\Aexamples/(?P<id>.*).json\Z')
def examples_star_json(name, match):
    def action(t):
        content = json.dumps({
            'id': match.group('id'),
            'inherits': '../base.json',
            'inputs': [
                'examples/%(id)s.js' % match.groupdict(),
                'build/src/internal/src/types.js',
            ],
        })
        with open(t.name, 'w') as f:
            f.write(content)
    dependencies = [__file__, 'base.json']
    return pake.Target(name, action=action, dependencies=dependencies)


@pake.rule(r'\Aexamples/(?P<id>.*).combined.js\Z')
def examples_star_combined_js(name, match):
    def action(t):
        t.output('java', '-jar', PLOVR_JAR, 'build', 'examples/%(id)s.json' % match.groupdict())
        report_sizes(t)
    dependencies = [PLOVR_JAR, SRC, INTERNAL_SRC, 'base.json', 'examples/%(id)s.js' % match.groupdict(), 'examples/%(id)s.json' % match.groupdict()]
    return pake.Target(name, action=action, dependencies=dependencies)


@pake.target('serve', PLOVR_JAR, INTERNAL_SRC, 'examples')
def serve(t):
    t.run('java', '-jar', PLOVR_JAR, 'serve', glob.glob('build/*.json'), glob.glob('examples/*.json'))


@pake.target('serve-precommit', PLOVR_JAR, INTERNAL_SRC)
def serve_precommit(t):
    t.run('java', '-jar', PLOVR_JAR, 'serve', 'build/ol-all.json')


pake.virtual('lint', 'build/lint-src-timestamp', 'build/lint-spec-timestamp')


@pake.target('build/lint-src-timestamp', SRC, INTERNAL_SRC, EXTERNAL_SRC, EXAMPLES_SRC)
def build_lint_src_timestamp(t):
    limited_doc_files = [path
                         for path in pake.ifind('externs', 'build/src/external/externs')
                         if path.endswith('.js')]
    t.run('gjslint', '--strict', '--limited_doc_files=%s' % (','.join(limited_doc_files),), SRC, INTERNAL_SRC, EXTERNAL_SRC, EXAMPLES_SRC)
    t.touch()


@pake.target('build/lint-spec-timestamp', SPEC)
def build_lint_spec_timestamp(t):
    t.run('gjslint', SPEC)
    t.touch()


pake.virtual('plovr', PLOVR_JAR)


@pake.target(PLOVR_JAR, clean=False)
def plovr_jar(t):
    import urllib2
    url = 'https://plovr.googlecode.com/files/' + os.path.basename(PLOVR_JAR)
    content = urllib2.urlopen(url).read()
    with open(t.name, 'w') as f:
        f.write(content)


@pake.target('gh-pages', phony=True)
def gh_pages(t):
    t.run('bin/git-update-ghpages', 'openlayers/ol3', '-i', 'build/gh-pages/%(BRANCH)s' % globals(), '-p', BRANCH)


pake.virtual('doc', 'build/jsdoc-%(BRANCH)s-timestamp' % globals())


@pake.target('build/jsdoc-%(BRANCH)s-timestamp' % globals(), SRC, pake.ifind('doc/template'))
def jsdoc_BRANCH_timestamp(t):
    t.run(pake.variables['JSDOC'], '-t', 'doc/template', '-r', 'src', '-d', 'build/gh-pages/%(BRANCH)s/apidoc' % globals())
    t.touch()


@pake.target('hostexamples', 'build', 'examples', phony=True)
def hostexamples(t):
    t.makedirs('build/gh-pages/%(BRANCH)s/examples' % globals())
    t.makedirs('build/gh-pages/%(BRANCH)s/build' % globals())
    t.cp(EXAMPLES, (path.replace('.html', '.js') for path in EXAMPLES), 'examples/style.css', 'build/gh-pages/%(BRANCH)s/examples/' % globals())
    t.cp('build/loader_hosted_examples.js', 'build/gh-pages/%(BRANCH)s/examples/loader.js' % globals())
    t.cp('build/ol.js', 'build/ol.css', 'build/gh-pages/%(BRANCH)s/build/' % globals())
    t.cp('examples/example-list.html', 'build/gh-pages/%(BRANCH)s/examples/index.html' % globals())
    t.cp('examples/example-list.js', 'examples/example-list.xml', 'examples/Jugl.js', 'build/gh-pages/%(BRANCH)s/examples/' % globals())


@pake.target('test', INTERNAL_SRC, phony=True)
def test(t):
    t.run(pake.variables['PHANTOMJS'], 'test/phantom-jasmine/run_jasmine_test.coffee', 'test/ol.html')


if __name__ == '__main__':
    pake.main()
