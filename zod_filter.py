#!/usr/bin/env python3
"""
convert zod tiles to enlarge male clipping parts which were too loose for me.
see https://www.thingiverse.com/thing:2528937
just give a list of your tiles as command line arguments.
scales up by 1.25 which is the right value for me.

this is "scripty" at least. there is absolutely no guarantee that the parts detection
will work on all possible tiles. be sure to check your results.

author: frederic wagner (frederic dot wagner at imag dot fr)
license: gplv3
"""
from os.path import splitext
from sys import argv
from itertools import permutations
import struct
from collections import defaultdict
from math import sqrt

class Point:
    """
    point in space.
    """
    def __init__(self, coordinates):
        """
        build new point using an array of coordinates.
        """
        self.coordinates = coordinates

    def inflate_parts(self, spots, factor):
        """
        inflate each point around each spot by given factor.
        """
        for spot in spots:
            near_spot = True
            for index, coordinates in enumerate(zip(self.coordinates, spot[0].coordinates)):
                if index != spot[1]:
                    if abs(coordinates[0] - coordinates[1]) > 2.9:
                        near_spot = False
                        break
            if near_spot:
                for index, coordinates in enumerate(zip(self.coordinates, spot[0].coordinates)):
                    if index != spot[1]:
                        self.coordinates[index] = (coordinates[0] - coordinates[1]) *\
                                factor + coordinates[1]
                return True
        return False

    def __add__(self, other):
        """
        addition operator. (useful for translations)
        """
        return Point([i + j
                      for i, j in zip(self.coordinates, other.coordinates)])

    def __sub__(self, other):
        """
        substraction operator. (useful for translations)
        """
        return Point([i - j
                      for i, j in zip(self.coordinates, other.coordinates)])

    def __mul__(self, factor):
        """
        multiplication by scalar operator. (useful for scaling)
        """
        return Point([c*factor for c in self.coordinates])

    def __truediv__(self, factor):
        """
        division by scalar operator. (useful for scaling)
        """
        return Point([c/factor for c in self.coordinates])

    def scalar_product(self, other):
        """
        scalar (dot) product between two vectors
        """
        return sum([c1*c2
                    for c1, c2 in zip(self.coordinates, other.coordinates)])

class Facet:
    """
    facet in stl file (three ordered 3d points)
    """
    def __init__(self, points):
        self.points = points
        self.colored = False

    def inflate_parts(self, spots, factor):
        for point in self.points:
            if point.inflate_parts(spots, factor):
                self.colored = True

    def normal(self):
        """
        return normal vector
        """
        center = sum(self.points, Point([0.0, 0.0, 0.0]))/3
        u1 = self.points[0] - center
        u2 = self.points[1] - center
        normal = Point([
            u1.coordinates[1]*u2.coordinates[2] - u1.coordinates[2]*u2.coordinates[1],
            u1.coordinates[2]*u2.coordinates[0] - u1.coordinates[0]*u2.coordinates[2],
            u1.coordinates[0]*u2.coordinates[1] - u1.coordinates[1]*u2.coordinates[0],
            ])
        norm = sqrt(normal.scalar_product(normal))
        return normal / norm

def binary_facet(all_coordinates):
    """
    parses a facet in a binary stl file.
    """
    return Facet([Point(list(all_coordinates[3+3*i:6+3*i])) for i in range(3)])


class Stl:
    """
    stl files are a set of 3d facets
    """
    def __init__(self, file_name):
        self.facets = []
        self.parse_binary_stl(file_name)

    def points(self):
        """
        iterate on all our points
        """
        for facet in self.facets:
            for point in facet.points:
                yield point

    def detect_parts(self):
        """
        detect all parts to inflate.
        we detect them by their specific thickness.
        return spots where to scale (pillar around given center in given dimension).
        it could be improved but it's good enough.
        """
        spots = []
        for scanning, slicing in permutations(range(3), r=2):
            # figure out thickness when scanning in 2d
            limits = defaultdict(lambda: [float("inf"), float("-inf")])
            free_dimension = next(d for d in range(3) if d != scanning and d != slicing)
            for point in self.points():
                coordinate = point.coordinates[slicing]
                key = round(point.coordinates[scanning]*20.0)/20.0
                extremum = limits[key]
                extremum[0] = min(coordinate, extremum[0])
                extremum[1] = max(coordinate, extremum[1])
            for (coordinate, extremum) in limits.items():
                size = extremum[1] - extremum[0]
                if 2.29 <= size <= 2.36:
                    # male parts have this thickness
                    coordinates = [0.0, 0.0, 0.0]
                    coordinates[scanning] = coordinate
                    coordinates[slicing] = (extremum[0]+extremum[1])/2.0
                    spots.append((Point(coordinates), free_dimension))

        return spots

    def inflate_parts(self, spots, factor):
        """
        any point neat a spot gets scaled by given factor.
        """
        for facet in self.facets:
            facet.inflate_parts(spots, factor)

    def parse_binary_stl(self, file_name):
        """
        load binary stl file (basic)
        """
        with open(file_name, "rb") as stl_file:
            stl_file.read(80)
            packed_size = stl_file.read(4)
            if not packed_size:
                return False
            size_struct = struct.Struct('I')
            size = size_struct.unpack(packed_size)[0]
            facet_struct = struct.Struct('12fh')
            for _ in range(size):
                data = stl_file.read(4*3*4+2)
                #  for each facet : 4 vectors of 3 floats + 2 unused bytes
                fields = facet_struct.unpack(data)
                new_facet = binary_facet(fields)
                self.facets.append(new_facet)

    def save_binary_stl(self, file_name):
        """
        save binary stl file
        """
        with open(file_name, "wb") as stl_file:
            stl_file.write(b"\0"*80)
            size_struct = struct.Struct('I')
            stl_file.write(size_struct.pack(len(self.facets)))
            facet_struct = struct.Struct('12fH')
            red = 63489
            blue = 14185
            for facet in self.facets:
                color = red if facet.colored else blue
                stl_file.write(
                    facet_struct.pack(
                        *facet.normal().coordinates,
                        *facet.points[0].coordinates,
                        *facet.points[1].coordinates,
                        *facet.points[2].coordinates,
                        color,)
                    )

def main():
    """
    scales up each given files
    """
    files = argv[1:]
    for stl_file in files:
        print("loading stl file", stl_file)
        stl = Stl(stl_file)
        print("detecting parts to scale up")
        spots = stl.detect_parts()
        print(len(spots), "parts detected")
        if spots:
            print("scaling up")
            stl.inflate_parts(spots, 1.15)
            base, extension = splitext(stl_file)
            new_filename = base + "_big_" + extension
            print("saving scaled up model as", new_filename)
            stl.save_binary_stl(new_filename)
            print("done")

main()
