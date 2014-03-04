#!/usr/bin/env python
"""This file will take you all the way from a CSV of student performance on
test items to trained parameters describing the difficulties of the assessment
items.
The parameters can be used to identify the different concepts in your
assessment items, and to drive your own adaptive test. The mirt_engine python
file included here can be used to run an adaptive pretest that will provide an
adaptive set of assessment items if you provide information about whether the
questions are being answered correctly or incorrectly.

Example Use:
    with a file called my_data.csv call
    ./start_mirt_pipeline -i path/to/my_data.csv
    let a1_time.json be the name of the output json file
        (Congrats! Examine that for information about item difficulty!)

    To run an adaptive test with your test items:
    ./run_adaptive_test.py -i a1_time.json
    This will open an interactive session where the test will ask you questions
    according to whatever will cause the model to gain the most information to
    predict your abilities.
"""
import argparse
import datetime
import multiprocessing
import os
import shutil
import sys

from mirt import mirt_train_EM, generate_predictions
from mirt import visualize, adaptive_pretest, generate_responses
from train_util import model_training_util

# Necessary on some systems to make sure all cores are used. If not all
# cores are being used and you'd like a speedup, pip install affinity
try:
    import affinity
    affinity.set_process_affinity_mask(0, 2 ** multiprocessing.cpu_count() - 1)
except NotImplementedError:
    pass
except ImportError:
    sys.stderr.write('If you find that not all cores are being '
                    'used, try installing affinity.\n')


def get_command_line_arguments(arguments=None):
    """Gets command line arguments passed in when called, or
    can be called from within a program.

    Parses input from the command line into options for running
    the MIRT model. For more fine-grained options, look at
    mirt_train_EM.py
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true",
                        help=("Generate fake training data."))
    parser.add_argument("--train", action="store_true",
                        help=("Train a model from training data."))
    parser.add_argument("--visualize", action="store_true",
                        help=("Visualize a trained model."))
    parser.add_argument("--test", action="store_true",
                        help=("Take an adaptive test from a trained model."))
    parser.add_argument(
        "-d", "--data_file",
        default=os.path.dirname(
            os.path.abspath(__file__)) + '/sample_data/all.responses',
        help=("Name of file where data of interest is located."))
    parser.add_argument(
        '-a', '--abilities', default=1, type=int,
        help='The dimensionality/number of abilities.')
    parser.add_argument(
        '-s', '--num_students', default=500, type=int,
        help="Number of students to generate data for. Only meaningful when "
        "generating fake data - otherwise it's read from the data file.")
    parser.add_argument(
        '-p', '--num_problems', default=10, type=int,
        help="Number of problems to generate data for. Only meaningful when "
        "generating fake data - otherwise it's read from the data file.")
    parser.add_argument("-t", "--time", action="store_true",
                        help=("Generate fake training data."))
    parser.add_argument(
        '-w', '--workers', type=int, default=1,
        help=("The number of processes to use to parallelize mirt training"))
    parser.add_argument(
        "-n", "--num_epochs", type=int, default=100,
        help=("The number of EM iterations to do during learning"))
    parser.add_argument(
        "-o", "--model_directory",
        default=os.path.dirname(
            os.path.abspath(__file__)) + '/sample_data/models/',
        help=("The directory to write models and other output"))
    parser.add_argument(
        "-m", "--model",
        default=os.path.dirname(
            os.path.abspath(__file__)) + '/sample_data/models/model.json',
        help=("The location of the model (to write if training, and to read if"
              " visualizing or testing."))

    if arguments:
        arguments = parser.parse_args(arguments)
    else:
        arguments = parser.parse_args()

    # if we haven't been instructed to do anything, then show the help text
    if not (arguments.generate or arguments.train
            or arguments.visualize or arguments.test):
        print "\nMust specify at least one task " + \
            "(--generate, --train, --visualize, --test).\n"
        parser.print_help()

    # Save the current time for reference when looking at generated models.
    arguments.datetime = str(datetime.datetime.now())

    return arguments


def save_model(arguments):
    """Look at all generated models, and save the most recent to the correct
    location"""
    latest_model = get_latest_parameter_file_name(arguments)
    #with open(latest_model, 'r') as latest_model:
    #    with open(arguments.model, 'w') as model_location:
    if True:
        print "Saving model to %s" % arguments.model
        shutil.copyfile(latest_model, arguments.model)


def get_latest_parameter_file_name(arguments):
    """Get the most recent of many parameter files in a directory.

    There will be many .npz files written; we take the last one.
    """
    params = gen_param_str(arguments)
    path = arguments.model_directory + params + '/'
    npz_files = os.listdir(path)
    npz_files.sort(key=lambda fname: fname.split('_')[-1])
    return path + npz_files[-1]


def main():
    """Get arguments from the command line and runs with those arguments."""
    arguments = get_command_line_arguments()
    run_with_arguments(arguments)


def make_necessary_directories(arguments):
    """Ensure that output directories for the data we'll be writing exist."""
    roc_dir = arguments.model_directory + 'rocs/'
    model_training_util.mkdir_p([roc_dir])


def gen_param_str(arguments):
    """Transform data about current run into a param string for file names."""
    time_str = 'time' if arguments.time else 'no_time'
    return "%s_%s_%s" % (arguments.abilities, time_str, arguments.datetime)


def generate_model_with_parameters(arguments):
    """Trains a model with the given parameters, saving results."""
    param_str = gen_param_str(arguments)
    out_dir_name = arguments.model_directory + param_str + '/'
    model_training_util.mkdir_p(out_dir_name)
    # to set more fine-grained parameters about MIRT training, look at
    # the arguments at mirt/mirt_train_EM.py
    mirt_train_params = [
        '-a', str(arguments.abilities),
        '-w', str(arguments.workers),
        '-n', str(arguments.num_epochs),
        '-f', arguments.model_directory + 'train.responses',
        '-o', out_dir_name]
    if arguments.time:
        mirt_train_params.append('-z')

    mirt_train_EM.run_programmatically(mirt_train_params)


def generate_roc_curve_from_model(arguments):
    """Read results from each model trained and generate roc curves."""
    roc_dir = arguments.model_directory + 'rocs/'
    roc_file = roc_dir + arguments.datetime
    test_file = arguments.model_directory + 'test.responses'
    return generate_predictions.load_and_simulate_assessment(
        arguments.model, roc_file, test_file)


def run_with_arguments(arguments):
    """Takes you through every step from having a model, training it,
    testing it, and potentially uploading it to a testing engine.
    """
    params = gen_param_str(arguments)
    if arguments.generate:
        print 'Generating Responses'
        generate_responses.run(arguments)
        print 'Generated responses for %d students and %d ' % (
            arguments.num_students, arguments.num_problems)
    if arguments.train:
        # Set up directories
        make_necessary_directories(arguments)

        # Separate provided data file into a train and test set.
        model_training_util.sep_into_train_and_test(arguments)

        print 'Training MIRT models'
        # For each combination of the setting for "abilities" and
        # "response_time_mode", we want to fit a model.
        # Loop through the combinations and fit a model for each.
        generate_model_with_parameters(arguments)
        save_model(arguments)
        #out_dir_name = arguments.model_directory + params + '/'
        #model = get_latest_parameter_file_name(out_dir_name)

    if arguments.visualize:
        # TODO should make_necessary_directories(arguments) be called
        # here too?
        roc_curve = generate_roc_curve_from_model(arguments)
        print 'visualizing for %s' % arguments.model
        visualize.show_roc({params: [r for r in roc_curve]})
        visualize.show_exercises(arguments.model)

    if arguments.test:
        adaptive_pretest.main(arguments.model)

if __name__ == '__main__':
    main()
