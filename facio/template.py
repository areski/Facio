#!/usr/bin/env python

import os
import re
import tempfile

from shutil import copytree, move, rmtree, copy


class Template(object):

    def __init__(self, config):
        # Setting defults
        self.is_git = False
        self.complete = False
        self.exclude_dirs = ['.git', '.hg']
        self.place_holders = {
            'PROJECT_NAME': 'project_name',
            'SETTINGS_DIR': 'template_settings_dir',
            'DJANGO_SECRET_KEY': 'django_secret_key'}

        # Load Config
        self.config = config
        # Set place holder vars from config
        self.set_template_variables()
        # Add custom varibles if provided
        if hasattr(self.config, 'variables'):
            self.add_custom_vars()
        # Set the project root
        self.set_project_root()
        # Git detection
        self._is_git()

    @property
    def working_dir(self):
        return os.popen('pwd').read().split()[0]

    def add_custom_vars(self):
        ''' Add custom variables to place holders. '''

        # TODO: Needs validation
        pairs = self.config.variables.split(',')
        for pair in pairs:
            try:
                place_holder, value = pair.split('=')
            except ValueError:
                pass  # If its not formatted correctly, we ignore it
            else:
                self.place_holders[place_holder] = value

    def set_project_root(self):
        '''Set project root, based on working dir and project name.'''

        self.project_root = os.path.join(self.working_dir,
                                         self.config.project_name)

    def make_project_dir(self):
        '''Make the project director in current working directory.'''

        if not os.path.isdir(self.project_root):
            os.mkdir(self.project_root)
            if not os.path.isdir(self.project_root):
                self.config.cli_opts.error('Error creating project '
                                           'directory')
        else:
            self.config.cli_opts.error('%s already exists' % (
                self.project_root))

    def set_template_variables(self):
        ''' Replace self.place_holders defaults w/ config values. '''

        for place_holder in self.place_holders:
            config_value = getattr(self.config,
                                   self.place_holders[place_holder], None)
            if config_value:
                self.place_holders[place_holder] = config_value

# TODO: git stuff should live in its own class
    def _is_git(self):
        '''Detect if the user wants to use a git repository.'''

        if self.config.template.startswith('git+'):
            self.is_git = True
            self.git_repo_path = self.config.template.replace('git+', '')
            self.config.template = tempfile.mkdtemp(suffix='facio')
            print 'Using git to clone template from %s' % self.git_repo_path
            self.git_clone()

    def git_clone(self):
        '''Clone git repository into tmp directory.'''
        try:
            from git import Repo
        except ImportError:  # pragma: no cover
            self.config.cli_opts.error('GitPython module missing, '
                                       'please install it.')

        try:
            repo = Repo.init(self.config.template)
            repo.create_remote('origin', self.git_repo_path)
            origin = repo.remotes.origin
            origin.fetch()
            origin.pull('master')
        except:
            self.config.cli_opts.error('Error cloning repository')
        else:
            rmtree(os.path.join(self.config.template, '.git'))

    def copy_template(self):
        '''Moves template into current working dir.'''

        if os.path.isdir(self.config.template):
            self.make_project_dir()
            for file in os.listdir(self.config.template):
                path = os.path.join(self.config.template, file)
                dirs = path.split('/')
                exclude = False
                for dir in dirs:
                    if dir in self.exclude_dirs:
                        exclude = True
                if not exclude:
                    if os.path.isdir(path):
                        copytree(path, os.path.join(self.project_root, file))
                    else:
                        copy(path, self.project_root)
            self.swap_placeholders()
        else:
            self.config.cli_opts.error('Unable to copy template, directory '
                                       'does not exist')

        if self.is_git:
            rmtree(self.config.template)

    def rename(self, root, name):
        '''Rename a file or directory.'''

        e = re.compile(r'__(.*?)__')
        try:
            plain = e.findall(name)[0]
            if plain in self.place_holders:
                place_holder_val = self.place_holders[plain]
                origin = os.path.join(root, name)
                new_name = name.replace('__%s__' % plain, place_holder_val)
                new = os.path.join(root, new_name)
                move(origin, new)
                return True
            else:
                return False
        except IndexError:
            pass

    def rename_directories(self):
        '''Move directories with placeholder names.'''

        for root, dirs, files in os.walk(self.project_root):
            for d in dirs:
                filepath = os.path.join(root, d)
                if os.path.isdir(filepath):
                    if self.rename(root, d):
                        self.rename_directories()
        return False

    def rename_files(self):
        '''Move files with placeholder names.'''

        for root, dirs, files in os.walk(self.project_root):
            for f in files:
                filepath = os.path.join(root, f)
                if os.path.isfile(filepath):
                    if self.rename(root, f):
                        self.rename_files()
        return False

    def swap_placeholders(self):
        '''Swap placeholders for real values.'''

        try:
            from jinja2 import Environment, FileSystemLoader
        except ImportError:  # pragma: no cover
            self.config.cli_opts.error('Jinja2 is required for tempalte '
                                       'processing, please install it.')

        while self.rename_directories():
            continue  # pragma: no cover

        while self.rename_files():
            continue  # pragma: no cover

        for root, dirs, files in os.walk(self.project_root):
            jinja_tpl_loader = FileSystemLoader(root)
            jinja_env = Environment(loader=jinja_tpl_loader)
            for f in files:
                filepath = os.path.join(root, f)
                exclude = False
                dirs = filepath.split('/')
                for d in dirs:
                    if d in self.exclude_dirs:
                        exclude = True  # pragma: no cover
                if not exclude:
                    tpl = jinja_env.get_template(f)
                    file_contents = tpl.render(self.place_holders)
                    with open(filepath, 'w') as f:
                        f.write(file_contents)