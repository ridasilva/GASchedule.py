from model.Criteria import Criteria
from model.Schedule import Schedule
import numpy as np
import random
import sys
from time import time


# Deb K , Jain H . An Evolutionary Many-Objective Optimization Algorithm Using Reference Point-Based Nondominated Sorting Approach,
# Part I: Solving Problems With Box Constraints[J]. IEEE Transactions on Evolutionary Computation, 2014, 18(4):577-601.
# Copyright (c) 2023 Miller Cy Chan


# NSGA III
class NsgaIII:
    def initAlgorithm(self, prototype, numberOfChromosomes=100):
        # Prototype of chromosomes in population
        self._prototype = prototype

        # there should be at least 2 chromosomes in population
        if numberOfChromosomes < 2:
            numberOfChromosomes = 2

        # Best of chromosomes
        self._best = None
        self._populationSize = numberOfChromosomes

    # Initializes genetic algorithm
    def __init__(self, configuration, numberOfCrossoverPoints=2, mutationSize=2, crossoverProbability=80,
                 mutationProbability=3):
        self.initAlgorithm(Schedule(configuration))
        self._mutationSize = mutationSize
        self._numberOfCrossoverPoints = numberOfCrossoverPoints
        self._crossoverProbability = crossoverProbability
        self._mutationProbability = mutationProbability

        self._objDivision = []
        if len(Criteria.weights) < 8:
            self._objDivision.append(6)
        else:
            self._objDivision.append(3)
            self._objDivision.append(2)

    @property
    # Returns pointer to best chromosomes in population
    def result(self):
        return self._best


    class ReferencePoint:
        def __init__(self, M):
            self.memberSize = 0
            self.position = np.zeros(M)
            self._potentialMembers = {}

        @staticmethod
        def generateRecursive(rps, pt, numObjs, left, total, element):
            if element == numObjs - 1:
                pt.position[element] = left * 1.0 / total
                rps.append(pt)
            else:
                for i in range(left + 1):
                    pt.position[element] = i * 1.0 / total
                    NsgaIII.ReferencePoint.generateRecursive(rps, pt, numObjs, left - i, total, element + 1)

        def addMember(self):
            self.memberSize += 1

        def addPotentialMember(self, memberInd, distance):
            currDistance = self._potentialMembers.get(memberInd)
            if currDistance is None or distance < currDistance:
                self._potentialMembers[memberInd] = distance

        def findClosestMember(self):
            minDist, minIndv = sys.float_info.max, -1
            for k, v in self._potentialMembers.items():
                if v < minDist:
                    minDist, minIndv = v, k
            return minIndv

        def hasPotentialMember(self):
            return bool(self._potentialMembers)

        def randomMember(self):
            if not self.hasPotentialMember():
                return -1

            members = list(self._potentialMembers.keys())
            return members[random.randrange(len(self._potentialMembers))]

        def removePotentialMember(self, memberInd):
            while memberInd in self._potentialMembers:
                del self._potentialMembers[memberInd]

        @staticmethod
        def generateReferencePoints(rps, M, p):
            pt = NsgaIII.ReferencePoint(M)
            NsgaIII.ReferencePoint.generateRecursive(rps, pt, M, p[0], p[0], 0)

            if len(p) > 1: # two layers of reference points (Check Fig. 4 in NSGA-III paper)
                insideRps = []
                NsgaIII.ReferencePoint.generateRecursive(insideRps, pt, M, p[1], p[1], 0)

                center = 1.0 / M
                for insideRp in insideRps:
                    for j, pos in enumerate(insideRp.position):
                        pos = center + pos / 2

                    rps.append(insideRp)



    def perpendicularDistance(self, direction, point):
        numerator, denominator = 0, 0
        for i, dir in enumerate(direction):
            numerator += dir * point[i]
            denominator += dir ** 2

        if denominator <= 0:
            return sys.float_info.max

        k, d = numerator / denominator, 0
        for i, dir in enumerate(direction):
            d += (k * dir - point[i]) ** 2

        return np.sqrt(d)

    def associate(self, rps, pop, fronts):
        for t, front in enumerate(fronts):
            for memberInd in front:
                minRp, minDist = len(rps) - 1, sys.float_info.max
                for r, rp in enumerate(rps):
                    d = self.perpendicularDistance(rp.position, pop[memberInd].convertedObjectives)
                    if d < minDist:
                        minRp, minDist = r, d

                if t + 1 != len(fronts):
                    rps[minRp].addMember()
                else:
                    rps[minRp].addPotentialMember(memberInd, minDist)

    def guassianElimination(self, A, b):
        N = len(A)
        for i in range(N):
            A[i].append(b[i])

        for base in range(N - 1):
            for target in range(base + 1, N):
                ratio = A[target][base] / A[base][base]
                for term in range(len(A[base])):
                    A[target][term] -= A[base][term] * ratio

        x = np.zeros(N)
        for i in range(N - 1, -1, -1):
            for known in range(i + 1, N):
                A[i][N] -= A[i][known] * x[known]

            x[i] = A[i][N] / A[i][i]

        return x

    # ASF: Achivement Scalarization Function
    def ASF(self, objs, weight):
        max_ratio = -sys.float_info.max
        for f, obj in enumerate(objs):
            w = max(weight[f], 1e-6)
            max_ratio = max(max_ratio, obj / w)

        return max_ratio

    def findExtremePoints(self, pop, fronts):
        numObj = len(pop[0].objectives)

        exp = []
        for f in range(numObj):
            w = np.full(numObj, 1e-6)
            w[f] = 1.0

            minASF, minIndv = sys.float_info.max, len(fronts[0])

            for frontIndv in fronts[0]:
                asf = self.ASF(pop[frontIndv].convertedObjectives, w)

                if asf < minASF:
                    minASF, minIndv = asf, frontIndv

            exp.append(minIndv)

        return exp

    def findMaxObjectives(self, pop):
        numObj = len(pop[0].objectives)
        maxPoint = np.full(numObj, -sys.float_info.max)
        for chromosome in pop:
            for f, point in enumerate(maxPoint):
                point = max(point, chromosome.objectives[f])

        return maxPoint

    def findNicheReferencePoint(self, rps):
        # find the minimal cluster size
        minSize = sys.float_info.max
        for rp in rps:
            minSize = min(minSize, rp.memberSize)

        # find the reference points with the minimal cluster size Jmin
        min_rps = []
        for r, rp in enumerate(rps):
            if rp.memberSize == minSize:
                min_rps.append(r)

        # return a random reference point (j-bar)
        return min_rps[random.randrange(len(min_rps))]

    def constructHyperplane(self, pop, extremePoints):
        numObj = len(pop[0].objectives)
        # Check whether there are duplicate extreme points.
        # This might happen but the original paper does not mention how to deal with it.
        duplicate = False
        for i, extremePoint in enumerate(extremePoints):
            if duplicate:
                break
            for j in range(i + 1, len(extremePoints)):
                if duplicate:
                    break
                duplicate = (extremePoint == extremePoints[j])

        intercepts, negativeIntercept = [], False
        if not duplicate:
            # Find the equation of the hyperplane
            b, A = np.ones(numObj), [[] * len(extremePoints)]
            for p, extremePoint in enumerate(extremePoints):
                A[p] = pop[extremePoint].convertedObjectives

            x = self.guassianElimination(A, b)
            # Find intercepts
            for f in range(numObj):
                intercepts.append(1.0 / x[f])

                if x[f] < 0:
                    negativeIntercept = True
                    break

        if duplicate or negativeIntercept: # follow the method in Yuan et al. (GECCO 2015)
            intercepts = self.findMaxObjectives(pop)

        return intercepts


    def normalizeObjectives(self, pop, fronts, intercepts, idealPoint):
        for front in fronts:
            for i, ind in enumerate(front):
                convObjs = pop[ind].convertedObjectives
                for f, convObj in enumerate(convObjs):
                    if abs(intercepts[f] - idealPoint[f]) > np.finfo(float).eps: # avoid the divide-by-zero error
                        convObj /= intercepts[f] - idealPoint[f]
                    else:
                        convObj /= np.finfo(float).eps

    def dominate(self, left, right):
        better = False
        for f, leftObj in enumerate(left.objectives):
            if leftObj > right.objectives[f]:
                return False

            if leftObj < right.objectives[f]:
                better = True

        return better

    def nondominatedSort(self, pop):
        numAssignedIndividuals, rank = 0, 1
        fronts, indvRanks = [], np.zeros(len(pop))

        while numAssignedIndividuals < len(pop):
            curFront = []
	
            for i, chromosome in enumerate(pop):
                if indvRanks[i] > 0:
                    continue # already assigned a rank

                be_dominated = False
                for j, front in enumerate(curFront):
                    if self.dominate(pop[front], chromosome):
                        be_dominated = True
                        break
                    elif self.dominate(chromosome, pop[front]):
                        del curFront[j]

                if not be_dominated:
                    curFront.append(i)

            for front in curFront:
                indvRanks[front] = rank

            fronts.append(curFront)
            numAssignedIndividuals += len(curFront)

            rank += 1

        return fronts

    def selectClusterMember(self, rp):
        if rp.hasPotentialMember():
            if rp.memberSize == 0: # currently has no member
                return rp.findClosestMember()

            return rp.randomMember()

        return -1

    def translateObjectives(self, pop, fronts):
        idealPoint, numObj = [], len(pop[0].objectives)
        for f in range(numObj):
            minf = sys.float_info.max
            for frontIndv in fronts[0]: # min values must appear in the first front
                minf = min(minf, pop[frontIndv].objectives[f])

            idealPoint.append(minf)

            for front in fronts:
                for ind in front:
                    pop[ind].resizeConvertedObjectives(numObj)
                    convertedObjectives = pop[ind].convertedObjectives
                    convertedObjectives[f] = pop[ind].objectives[f] - minf

        return idealPoint

    def doSelection(self, cur, rps):
        next = []

        # ---------- Step 4 in Algorithm 1: non-dominated sorting ----------
        fronts = self.nondominatedSort(cur)

        # ---------- Steps 5-7 in Algorithm 1 ----------
        last, next_size = 0, 0
        while next_size < self._populationSize:
            next_size += len(fronts[last])
            last += 1

        fronts = fronts[: last] # remove useless individuals

        for t in range(len(fronts) - 1):
            for frontIndv in fronts[t]:
                next.append(cur[frontIndv])

        # ---------- Steps 9-10 in Algorithm 1 ----------
        if len(next) == self._populationSize:
            next.sort(key = lambda chromosome: chromosome.fitness, reverse=True)
            return next

        # ---------- Step 14 / Algorithm 2 ----------
        idealPoint = self.translateObjectives(cur, fronts)

        extremePoints = self.findExtremePoints(cur, fronts)

        intercepts = self.constructHyperplane(cur, extremePoints)

        self.normalizeObjectives(cur, fronts, intercepts, idealPoint)

        # ---------- Step 15 / Algorithm 3, Step 16 ----------
        self.associate(rps, cur, fronts)

        # ---------- Step 17 / Algorithm 4 ----------
        while len(next) < self._populationSize:
            minRp = self.findNicheReferencePoint(rps)

            chosen = self.selectClusterMember(rps[minRp])
            if chosen < 0: # no potential member in Fl, disregard this reference point
                del rps[minRp]
            else:
                rps[minRp].addMember()
                rps[minRp].removePotentialMember(chosen)
                next.append(cur[chosen])

        next.sort(key = lambda chromosome: chromosome.fitness, reverse=True)
        return next

    def replacement(self, population):
        populationSize = self._populationSize
        crossoverProbability, numberOfCrossoverPoints = self._crossoverProbability, self._numberOfCrossoverPoints
        offspring = []

        for i in range(0, populationSize, 2):
            father = population[random.randrange(populationSize)]
            mother = population[random.randrange(populationSize)]
            child0 = father.crossover(mother, numberOfCrossoverPoints, crossoverProbability)
            child1 = mother.crossover(father, numberOfCrossoverPoints, crossoverProbability)

            # append child chromosome to offspring list
            offspring.extend((child0, child1))

        return offspring


    # initialize new population with chromosomes randomly built using prototype
    def initialize(self, population):
        prototype = self._prototype

        for i in range(len(population)):
            # add new chromosome to population
            population[i] = prototype.makeNewFromPrototype()

    def reform(self):
        random.seed(round(time() * 1000))
        np.random.seed(int(time()))
        if self._crossoverProbability < 95:
            self._crossoverProbability += 1.0
        elif self._mutationProbability < 30:
            self._mutationProbability += 1.0

    def selection(self, population):
        rps = []
        self.ReferencePoint.generateReferencePoints(rps, len(Criteria.weights), self._objDivision)
        return self.doSelection(population, rps)

    # Starts and executes algorithm
    def run(self, maxRepeat=9999, minFitness=0.999):
        mutationSize, mutationProbability = self._mutationSize, self._mutationProbability
        populationSize = self._populationSize
        population = populationSize * [None]

        self.initialize(population)
        random.seed(round(time() * 1000))
        np.random.seed(int(time()))
        pop = [population, None]

        # Current generation
        currentGeneration = 0

        repeat = 0
        lastBestFit = 0.0

        cur, next = 0, 1
        while 1:
            if currentGeneration > 0:
                best = self.result
                print("Fitness:", "{:f}\t".format(best.fitness), "Generation:", currentGeneration, end="\r")

                # algorithm has reached criteria?
                if best.fitness > minFitness:
                    break

                difference = abs(best.fitness - lastBestFit)
                if difference <= 0.0000001:
                    repeat += 1
                else:
                    repeat = 0

                if repeat > (maxRepeat / 50):
                    self.reform()

            # crossover
            offspring = self.replacement(pop[cur])

            # mutation
            for child in offspring:
                child.mutation(mutationSize, mutationProbability)

            pop[cur].extend(offspring)

            # selection
            pop[next] = self.selection(pop[cur])
            self._best = pop[next][0] if self.dominate(pop[next][0], pop[cur][0]) else pop[cur][0]

            # comparison
            if currentGeneration > 0:
                lastBestFit = best.fitness

            cur, next = next, cur
            currentGeneration += 1

    def __str__(self):
        return "NSGA III"