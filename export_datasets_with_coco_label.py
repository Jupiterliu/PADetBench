from ast import arg
from calendar import c
from re import T

from traitlets import default
import carla
import random
import math
import time
import os
import argparse
import sys
import keyboard
import numpy as np
import cv2
import json
from tick import Weather, Camera, Actor
from data_process import DatasetGenerator


def run(
        world,  # Name of the map
        settings,  # Settings for the dataset generation
        dataset_name = 'dataset',  # Define the dataset name
        save_path = 'data',  # Define the output directory
):
    
    # create a vehicle
    vehicle = Actor(world)

    # weather_update_freq = 0.1 / speed_weather_changing
    weather = Weather(world)

    # create a camera
    camera = Camera(world, vehicle)

    # Create the dataset generator
    datasetGenerator = DatasetGenerator(world, camera, save_path, dataset_name)
    
    iteration_len = len(settings['theta_list'])
    for i in range(iteration_len):
        vehicle.create_actor(settings['blueprint_list'][i], settings['spawnpoint_list'][i])
        camera.follow(vehicle)
        camera.rotate(settings['theta_list'][i], settings['phi_list'][i])
        camera.dolly(settings['radius_list'][i])
        
        print(settings['weather_list'][i])
        weather.tick(settings['weather_list'][i])

        sys.stdout.write('\r' + str(weather) + 12 * ' ')
        sys.stdout.flush()

        # Save the data in the pascal voc format
        # datasetGenerator.save_data(save_images=True, save_pascal_voc=True, save_images_with_2d_bb=True, save_images_with_3d_bb=True)
        datasetGenerator.save_data(save_images=True)

        if keyboard.is_pressed('q'):  
            print('You pressed q, loop will break')
            break  # exit loop
    
    datasetGenerator.annotation_save()

    # Destroy the vehicle
    del vehicle


def world_init(map):
    # Connect to the client and retrieve the world object
    client = carla.Client('localhost', 2000)
    world = client.load_world(map)

    # Set up the simulator in synchronous mode
    settings = world.get_settings()
    settings.synchronous_mode = True # Enables synchronous mode
    settings.fixed_delta_seconds = 0.05
    world.apply_settings(settings)

    return world

def world_close(world):
    settings = world.get_settings()
    settings.synchronous_mode = False # Enables synchronous mode
    world.apply_settings(settings)

def repeat_dataset(dataset, iterator):
    try:
        key = next(iterator)
        repeat_len = repeat_dataset(dataset, iterator)
        dataset[key] = np.repeat(dataset[key], repeat_len).tolist()
        return len(dataset[key])
    except StopIteration:
        return 1

def settings_complete(settings, grid=True):

    # default settings
    if 'spawnpoint_list' not in settings:
        settings['spawnpoint_list'] = [world.get_map().get_spawn_points()[0]]
    if 'blueprint_list' not in settings:
        settings['blueprint_list'] = [world.get_blueprint_library().filter('vehicle.*')[0]]
    if 'theta_list' not in settings:
        settings['theta_list'] = [math.pi/3]
    if 'phi_list' not in settings:
        settings['phi_list'] = [0]
    if 'radius_list' not in settings:
        settings['radius_list'] = [5]
    if 'weather_list' not in settings:
        settings['weather_list'] = [1000]

    if grid:
        # repeat the settings to match the dataset length
        dataset_len = repeat_dataset(settings, iter(settings))    
        
        # tile the settings to match the dataset length
        for key in settings:
            settings[key] = settings[key] * (dataset_len // len(settings[key]))

    return settings

if __name__ == '__main__':
    # Name the output directory with the rotation speed and the weather speed
    parser = argparse.ArgumentParser()
    parser.add_argument('--save_path', type=str, default='data', help='Name of the output directory')
    parser.add_argument('--map', type=str, default='Town10HD_Opt', help='Name of the map')
    parser.add_argument('--benchmark', type=str, choices=['vehicle', 'weather', 'distance', 'rotation-theta', 'rotation-phi', 'sphere', 'spot', 'random'], default='entire', help='Name of the benchmark')
    args = parser.parse_args()

    world = world_init(args.map)    

    # default settings
    default_dataset_len = 100
    settings = dict()

    # benchmark settings
    if args.benchmark == 'vehicle':
        dataset_name='vehicle'
        theta_len = 2
        phi_len = 4
        settings['blueprint_list'] = [blueprint for blueprint in world.get_blueprint_library().filter('vehicle.*')]
        settings['theta_list'] = [i/theta_len * (math.pi / 2) for i in range(1, theta_len + 1)] # without theta = 0, i.e., no overhead view
        settings['phi_list'] = [i/phi_len * (2 * math.pi) for i in range(phi_len)]

    if args.benchmark == 'spot':
        dataset_name='spot'
        settings['spawnpoint_list'] = world.get_map().get_spawn_points()
        settings['theta_list'] = [i/theta_len * (math.pi / 2) for i in range(theta_len)]
        settings['phi_list'] = [i/phi_len * (2 * math.pi) for i in range(phi_len)]

    if args.benchmark == 'rotation-theta':
        dataset_name='rotation-theta'
        settings['theta_list'] = [i/default_dataset_len * (math.pi / 2) for i in range(default_dataset_len)]
    if args.benchmark == 'rotation-phi':
        dataset_name='rotation-phi'
        settings['phi_list'] = [i/default_dataset_len * (2 * math.pi) for i in range(default_dataset_len)]
    if args.benchmark == 'sphere':
        dataset_name='sphere'
        decompose_dataset_len = int(default_dataset_len ** (1/2))
        settings['theta_list'] = [i/decompose_dataset_len * (math.pi / 2) for i in range(decompose_dataset_len)]
        settings['phi_list'] = [i/decompose_dataset_len * (2 * math.pi) for i in range(decompose_dataset_len)]
    if args.benchmark == 'distance':
        dataset_name='distance'
        settings['radius_list'] = [i/default_dataset_len * 10 + 4 for i in range(default_dataset_len)]
    if args.benchmark == 'weather':
        dataset_name='weather'
        settings['weather_list'] = [i * 10 for i in range(default_dataset_len)]
    
    settings = settings_complete(settings)

    run(world=world, settings=settings, dataset_name=dataset_name, save_path=args.save_path)

    world_close(world)
    