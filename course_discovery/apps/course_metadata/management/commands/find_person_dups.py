import argparse
import configparser
import hashlib
import logging
import pickle
import time
import urllib

from django.core.management import BaseCommand, CommandError
from edx_rest_api_client.client import EdxRestApiClient
from Levenshtein import distance

from course_discovery.apps.course_metadata.utils import MarketingSiteAPIClient


# Hello there. This management command is intended for manual runs only, against a remote API.

# reset; ./manage.py find_person_dups --auth-file ./auth.ini --strictness=unlikely --pickle-file ./find.pickle --csv-file ./find.csv


logger = logging.getLogger(__name__)

RED = "\033[1;31m"
BLUE = "\033[1;34m"
CYAN = "\033[1;36m"
GREEN = "\033[0;32m"
RESET = "\033[0;0m"
BOLD = "\033[;1m"


class PersonBucket(object):
    def __init__(self, person, levenshtein):
        self.people = [person]
        self.levenshtein = levenshtein

    def add_person_if_match(self, person):
        for p in self.people:
            if not self.is_match(person, p):
                return False
        self.people.append(person)
        return True

    # Override this in subclasses
    def is_match(self, person1, person2):
        return False

    def is_same_name(self, person1, person2):
        #print('MIKE checking names:', distance(person1['_full_name'], person2['_full_name']), self.levenshtein)
        if distance(person1['_full_name'], person2['_full_name']) <= self.levenshtein:
            return True

        if distance(person1['_complete_name'], person2['_complete_name']) <= self.levenshtein:
            return True

        return False

    def is_same_image(self, person1, person2):
        hash1 = person1['_image_hash']
        hash2 = person2['_image_hash']

        if hash1 is None or hash2 is None:
            return False

        return hash1 == hash2

    def is_same_email(self, person1, person2):
        email1 = person1['email']
        email2 = person2['email']

        if email1 is None or email1 == "" or email2 is None or email2 == "":
            return False

        return email1 == email2


class ExactMatchPersonBucket(PersonBucket):
    def is_match(self, person1, person2):
        results = (self.is_same_name(person1, person2),
                   self.is_same_image(person1, person2),
                   self.is_same_email(person1, person2))
        print('Comparing {} with {}: {}'.format(person1['_complete_name'], person2['_complete_name'], results))
        return all(results)


class MaybeMatchPersonBucket(PersonBucket):
    def is_match(self, person1, person2):
        return self.is_same_name(person1, person2) and (
                self.is_same_image(person1, person2) or self.is_same_email(person1, person2))


class UnlikelyMatchPersonBucket(PersonBucket):
    def is_match(self, person1, person2):
        return self.is_same_name(person1, person2)


class Command(BaseCommand):
    help = 'Find duplicate persons in course_metadata.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auth-file',
            default=None,
            type=argparse.FileType('r'),
            help='A file holding authentication tokens.'
        )
        parser.add_argument(
            '--levenshtein',
            action='store',
            type=int,
            default=0,
            help='The Levenshtein distance used to match names.'
        )
        parser.add_argument(
            '--strictness',
            action='store',
            choices=['exact', 'maybe', 'unlikely'],
            default='exact',
            help='How strict a comparison to use.'
        )
        parser.add_argument(
            '--csv-file',
            action='store',
            default=None,
            help='Save a CSV copy of the output in this file.'
        )
        parser.add_argument(
            '--pickle-file',
            action='store',
            default=None,
            help='A file to use as a saved discovery API result.'
        )

    def process_arguments(self, options):
        if options['auth_file'] is None:
            print('Please provide an --auth-file argument, pointing to an INI file like so:')
            print('')
            print('[DEFAULT]')
            print('oauth_url=...')
            print('oauth_id=...')
            print('oauth_secret=...')
            print('discovery_url=...')
            print('marketing_url=...')
            print('marketing_username=...')
            print('marketing_password=...')
            print('')
            raise CommandError('Missing --auth-file. See instructions above.')

        # Load auth values
        auth_parser = configparser.ConfigParser()
        auth_parser.read_file(options['auth_file'])

        def get_auth_data(key):
            val = auth_parser.get('DEFAULT', key)
            if val is None:
                raise CommandError('Missing key in auth-file: ' + key)
            options[key] = val

        get_auth_data('oauth_url')
        get_auth_data('oauth_id')
        get_auth_data('oauth_secret')
        get_auth_data('discovery_url')
        get_auth_data('marketing_url')
        get_auth_data('marketing_username')
        get_auth_data('marketing_password')

        return options

    def get_discovery_client(self):
        access_token, _ = EdxRestApiClient.get_oauth_access_token(
            self.options['oauth_url'],
            self.options['oauth_id'],
            self.options['oauth_secret'],
        )

        discovery_api_url = '{root}/api/v1/'.format(root=self.options['discovery_url'].strip('/'))
        return EdxRestApiClient(discovery_api_url, oauth_access_token=access_token)

    def get_marketing_client(self):
        return MarketingSiteAPIClient(self.options['marketing_username'],
                                      self.options['marketing_password'],
                                      self.options['marketing_url'])

    def get_people_from_discovery(self, client):
        everyone = []
        next_page = 1
        while next_page:
            people = client.people.get(page=next_page, page_size=200, include_course_runs_staffed=1,
                                       include_publisher_course_runs_staffed=1)
            for person in people['results']:
                everyone.append(person)
            next_page = next_page + 1 if people['next'] else None
        return everyone

    def add_calculated_data_to_people(self, people):
        def combine_names(*args):
            # Remove empty/None strings, then strip whitespace around them
            smoothed_args = filter(lambda a: a.strip(), filter(None, args))
            return ' '.join(smoothed_args)

        for person in people:
            # The ''.join(string.split) bit gets rid of all duplicate internal space
            person['_full_name'] = combine_names(person['given_name'], person['family_name'])
            person['_complete_name'] = combine_names(person['salutation'], person['_full_name'])

    def add_images_hashes_to_people(self, people):
        image_hashes = {}

        for person in people:
            url = person['profile_image_url']
            if url is None or url == '':
                person['_image_hash'] = None
                continue

            if url not in image_hashes:
                try:
                    # Specifying a user-agent avoids 403 errors (I guess Python's default agent has a bad rep)
                    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    f = urllib.request.urlopen(request)
                    image_hashes[url] = hashlib.sha256(f.read()).hexdigest()
                except urllib.error.URLError as e:
                    image_hashes[url] = None

            person['_image_hash'] = image_hashes[url]

    def add_marketing_data_to_people(self, people, marketing_client):
        node_url = marketing_client.api_url + '/node.json'
        for person in people:
            params = {'type': 'person', 'uuid': person['uuid']}
            marketing_data = marketing_client.api_session.get(node_url, params=params)
            if marketing_data.status_code != 200:
                raise Exception('Bad marketing response: ' + marketing_data.text)

            json_response = marketing_data.json()
            if not json_response['list']:
                person['_status'] = -1  # not used on drupal site - for us, this means no drupal node exists
                continue

            json_data = json_response['list'][0]
            person['_mktg'] = json_data
            person['_status'] = int(json_data['status'])

    def get_all_people(self):
        pickle_filename = self.options['pickle_file']
        if pickle_filename:
            try:
                everyone = pickle.load(open(pickle_filename, 'rb'))
                print('Loaded people from pickle file.')
                return everyone
            except Exception:
                pass

        discovery_client = self.get_discovery_client()
        marketing_client = self.get_marketing_client()

        start = time.perf_counter()
        everyone = self.get_people_from_discovery(discovery_client)
        self.add_calculated_data_to_people(everyone)
        self.add_images_hashes_to_people(everyone)
        self.add_marketing_data_to_people(everyone, marketing_client)
        end = time.perf_counter()
        print('Done loading people. Took {}.'.format(time.strftime('%H:%M:%S', time.gmtime(end - start))))

        if pickle_filename:
            pickle.dump(everyone, open(pickle_filename, 'wb', -1))

        return everyone

    def generate_bucket(self, person):
        strictness = self.options['strictness']
        if strictness == 'unlikely':
            return UnlikelyMatchPersonBucket(person, self.options['levenshtein'])
        elif strictness == 'maybe':
            return MaybeMatchPersonBucket(person, self.options['levenshtein'])
        else:
            return ExactMatchPersonBucket(person, self.options['levenshtein'])

    def determine_buckets(self, everyone):
        buckets = []

        for person in everyone:
            # Find a bucket for this person. If we can't, make a new one
            for bucket in buckets:
                if bucket.add_person_if_match(person):
                    break
            else:
                buckets.append(self.generate_bucket(person))

        return buckets

    def print_csv_fact(self, fact):
        if fact:
            quoted = '"{}"'.format(fact.replace('"', '""'))
        else:
            quoted = ''
        self.csv.write(quoted + ',')

    def print_csv_endline(self, extra=''):
        self.csv.write(extra + '\r\n')

    def print_fact(self, title, fact, color=RESET):
        print(BOLD + title + ': ' + RESET + color + ('' if fact is None else fact) + RESET)
        self.print_csv_fact(fact)

    def present_person(self, person, bucket, bad=False):

        staffed = len(person['course_runs_staffed'])
        staffed_keys = ','.join([x['key'] for x in person['course_runs_staffed']])
        publisher_staffed = len(person['publisher_course_runs_staffed'])
        bio = person['bio'] or ''
        position = person['position']

        self.print_fact('NAME', person['_complete_name'], CYAN)
        self.print_fact('   PAGE', 'http://www.edx.org/bio/' + person['slug'])
        self.print_fact('   EMAIL', person['email'])
        if position:
            self.print_fact('   POSITION', (position['title'] or 'null') + ' at ' + (position['organization_name'] or 'null'))
        else:
            self.print_fact('   POSITION', None)
        self.print_fact('   BIO', bio[0:60] + ('...' if len(bio) > 60 else ''))
        self.print_fact('   UUID', person['uuid'])

        if not staffed and not publisher_staffed:
            self.print_fact('   COURSES', 'none')
        elif staffed and not publisher_staffed:
            self.print_fact('   COURSES', '{} in disco'.format(staffed_keys))
        elif not staffed and publisher_staffed:
            self.print_fact('   COURSES', '{} in publisher only'.format(publisher_staffed))
        else:
            self.print_fact('   COURSES', '{} in disco, {} in publisher'.format(staffed_keys, publisher_staffed))

        if person['_status'] == 1:
            self.print_fact('   STATUS', 'published', GREEN)
        elif person['_status'] == -1:
            self.print_fact('   STATUS', 'not in drupal', RED)
        else:
            self.print_fact('   STATUS', 'unpublished', RED)

        if bad:
            self.print_fact('   RECOMMENDATION', 'delete', RED)

            published = list(filter(lambda p: p['_status'] == 1, bucket.people))
            #if len(published) == 1:
            self.print_fact('   DELETE SCRIPT ARG', person['uuid'] + ':' + published[0]['uuid'])
            #else:
            #    self.print_fact('   DELETE SCRIPT ARG', 'manual')
        else:
            self.print_csv_fact('')
            self.print_csv_fact('')

        self.print_csv_endline()

    def sort_buckets(self, buckets):
        single_count = 0
        all_published_count = 0
        multiple_published_count = 0
        good_buckets = []

        for bucket in buckets:
            if len(bucket.people) <= 1:
                #print('Skipping bucket with one person:', bucket.people[0]['_complete_name'])
                #self.present_person(bucket.people[0])
                single_count += 1
                continue

            if len(list(filter(lambda p: p['_status'] == 1, bucket.people))) > 1:
                multiple_published_count += 1

            if all([p['_status'] == 1 for p in bucket.people]):
                # All of these are published, ignore - TODO handle these sets better...
                all_published_count += 1
                #continue

            good_buckets.append(bucket)

        print('')
        print('Total number of grouped people:', len(buckets))
        print('People with no dups:', single_count)
        print('Grouped people where all duplicates are published:', all_published_count)
        print('Remaining grouped people with an unpublished duplicate:', len(good_buckets))
        print('Grouped people with multiple published duplicates:', multiple_published_count)

        return good_buckets

    def present_bucket(self, bucket):
        will_present = False

        def should_examine(p):
            # Not published
            # return p['_status'] < 1

            # Published
            # return p['_status'] == 1

            # Published, no courses
            return p['_status'] == 1 and \
                   not len(p['course_runs_staffed']) and \
                   not len(p['publisher_course_runs_staffed'])

            # Unpublished, with courses
            # return p['_status'] == 0 and \
            #        (len(p['course_runs_staffed']) or \
            #         len(p['publisher_course_runs_staffed']))

        for person in bucket.people:
            if should_examine(person):
                will_present = True
                break

        if will_present:
            print('')
            print('')
            self.print_csv_endline()
            self.print_csv_endline()

            good_people = []
            bad_people = []

            # print('Are these the same people?')
            for person in bucket.people:
                if should_examine(person):
                    bad_people.append(person)
                else:
                    good_people.append(person)

            for person in good_people:
                self.present_person(person, bucket, bad=False)

            print('-----')
            self.print_csv_endline('-----')

            for person in bad_people:
                self.present_person(person, bucket, bad=True)
                self.total_bad += 1

            #input('Press enter to continue.')

    def delete_duplicate(self, dup, real):
        # Only currently allow not-in-drupal deletions
        if dup['_status'] != -1:
            return

        #discovery_client = self.get_discovery_client()
        #discovery_client.people.delete(uuid=dup['uuid'])

    def handle(self, *args, **options):
        self.options = self.process_arguments(options)

        # Set up CSV file writer, so it's always writable
        csv_file = options['csv_file']
        self.csv = open(csv_file if csv_file else '/dev/null', mode='w')
        self.csv.write('Name,Bio Page,Email,Blurb,UUID,Courses,Status,Delete?\r\n')

        everyone = self.get_all_people()
        buckets = self.determine_buckets(everyone)
        buckets = self.sort_buckets(buckets)

        self.total_bad = 0
        for bucket in buckets:
            self.present_bucket(bucket)

        self.csv.close()

        print('')
        print('')
        print('Total duplicates to delete:', self.total_bad)
