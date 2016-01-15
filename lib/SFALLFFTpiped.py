import os
import struct
import sys
from PDBCURjob import PDBCURjob
from SFALLjob import SFALLjob
from FFTjob import FFTjob
from ENDjob import ENDjob
from MAPMASKjob import MAPMASKjob
from mapTools import mapTools
from logFile import logFile

class pipeline():

	def __init__(self,outputDir,inputFile,jobName):
		self.outputDir	= outputDir
		self.inputFile 	= inputFile
		self.jobName 	= jobName

	def runPipeline(self):

		# read input file first
		success = self.readInputFile()
		if success is False:
			return 1

		# create log file
		self.runLog = logFile('{}/{}_runLog_2.txt'.format(self.outputDir,self.jobName))

		# run pdbcur job 
		pdbcur = PDBCURjob(self.pdbcurPDBinputFile,self.outputDir,self.runLog)
		success = pdbcur.run()
		if success is False:
			return 2

		self.PDBCURoutputFile = pdbcur.outputPDBfile

		# reorder atoms in PDB file
		self.renumberPDBFile()

		# get space group from PDB file
		success = self.getSpaceGroup()
		if success is False:
			return 3

		# run SFALL job
		sfall = SFALLjob(self.reorderedPDBFile,self.outputDir,self.sfall_VDWR,
						 self.spaceGroup,self.sfall_GRID,'ATMMOD',self.runLog)
		success = sfall.run()
		if success is False:
			return 4

		# run FFT job
		sfallMap = mapTools(sfall.outputMapFile)
		axes = [sfallMap.fastaxis,sfallMap.medaxis,sfallMap.slowaxis]
		gridSamps = [sfallMap.gridsamp1,sfallMap.gridsamp2,sfallMap.gridsamp3]
		labelsInit = ['FP_'+self.initPDB,'SIGFP_'+self.initPDB,'FOM_'+self.initPDB,'PHIC_'+self.initPDB]
		labelsLater = ['FP_'+self.laterPDB,'SIGFP_'+self.laterPDB,'FOM_'+self.laterPDB,'PHIC_'+self.laterPDB]
		
		if self.densMapType != 'END':
			fft = FFTjob(self.densMapType,self.FOMweight,self.laterPDB,self.inputMtzFile,
						 self.outputDir,axes,gridSamps,labelsLater,labelsInit,self.runLog)
			success = fft.run()
		else:
			# run END job if required (may take time to run!!)
			endInputPDB = self.pdbcurPDBinputFile
			endInputMTZ = ''.join(endInputPDB.split('.')[:-1]+['.mtz'])
			endInputEFF = ''.join(endInputPDB.split('.')[:-1]+['.eff'])
			end = ENDjob(endInputPDB,endInputMTZ,endInputEFF,self.outputDir,gridSamps,self.runLog)
			success = end.run()

		if success is False:
			return 5

		# crop fft and atom-tagged maps to asymmetric unit:
		mapmask1 = MAPMASKjob(sfall.outputMapFile,'',self.outputDir,self.runLog)
		success = mapmask1.crop2AsymUnit()
		if success is False:
			return 6

		# choose correct density map to include in MAPMASK cropping below
		if self.densMapType != 'END':
			inputDensMap = fft.outputMapFile
		else: 
			inputDensMap = end.outputMapFile

		mapmask2 = MAPMASKjob(inputDensMap,'',self.outputDir,self.runLog)
		success = mapmask2.crop2AsymUnit()
		if success is False:
			return 7

		# run MAPMASK job to crop fft density map to same grid 
		# sampling dimensions as SFALL atom map
		mapmask3 = MAPMASKjob(mapmask2.outputMapFile,mapmask1.outputMapFile,self.outputDir,self.runLog)
		success = mapmask3.cropMap2Map()
		if success is False:
			return 8

		# perform map consistency check between cropped fft and sfall maps
		fftMap = mapTools(mapmask3.outputMapFile)
		fftMap.readHeader()
		sfallMap = mapTools(mapmask1.outputMapFile)
		sfallMap.readHeader()
		success = self.mapConsistencyCheck(sfallMap,fftMap)
		if success is False:
			return 9
		else:
			return 0

	def readInputFile(self):
		# read in input file for pipeline

		# if Input.txt not found, flag error
		if os.path.isfile(self.inputFile) is False:
			print 'Required input file {} not found..'.format(self.inputFile)
			return False

		inputFile = open(self.inputFile,'r')

		self.sfall_GRID = []
		for line in inputFile.readlines():
			if 'END' == line.split()[0]:
				break
			if 'pdbIN' == line.split()[0]:
				self.pdbcurPDBinputFile = line.split()[1]
			if 'runname' == line.split()[0]:
				runname = line.split()[1]
			if 'sfall_GRID' == line.split()[0]:
				sfall_GRIDnx = line.split()[1]
				sfall_GRIDny = line.split()[2]
				sfall_GRIDnz = line.split()[3]
				self.sfall_GRID = [sfall_GRIDnx,sfall_GRIDny,sfall_GRIDnz]
			if 'sfall_VDWR' == line.split()[0]:
				self.sfall_VDWR = line.split()[1]
			if 'mtzIN' == line.split()[0]:
				self.inputMtzFile = line.split()[1]
			if 'foldername' == line.split()[0]:
				self.outputDir = line.split()[1]
			if 'initialPDB' == line.split()[0]:
				self.initPDB = line.split()[1]
			if 'laterPDB' == line.split()[0]:
				self.laterPDB = line.split()[1]
			if 'densMapType' == line.split()[0]:
				self.densMapType = line.split()[1]
			if 'FFTmapWeight' == line.split()[0]:
				self.FOMweight = line.split()[1]
		return True

	def renumberPDBFile(self):
		# reorder atoms in pdb file since some may be missing now after
		# pdbcur has been run
		self.runLog.writeToLog('Renumbering input pdb file: {}'.format(self.PDBCURoutputFile))
		self.reorderedPDBFile = (self.PDBCURoutputFile).split('_pdbcur.pdb')[0]+'_reordered.pdb'

		pdbin = open(self.PDBCURoutputFile,'r')
		pdbout = open(self.reorderedPDBFile,'w')

		counter = 0
		for line in pdbin.readlines():
			if ('ATOM' not in line[0:4] and 'HETATM' not in line[0:6]):
				pdbout.write(line)
			else:
				counter += 1
				pdbout.write(line[0:6])
				new_atomnum = " "*(5-len(str(counter))) + str(counter) #has length 5
				pdbout.write(new_atomnum)
				pdbout.write(line[11:80]+'\n')
		pdbin.close()
		pdbout.close()
		self.runLog.writeToLog('Output pdb file: {}'.format(self.reorderedPDBFile))

	def getSpaceGroup(self):
		pdbin = open(self.reorderedPDBFile,'r')
		for line in pdbin.readlines():
			if line.split()[0] == 'CRYST1':
				self.spaceGroup = line[55:66].replace(' ','')
				self.runLog.writeToLog('Retrieving space group from file: {}'.format(self.PDBCURoutputFile))
				self.runLog.writeToLog('Space group determined to be {}'.format(self.spaceGroup))
		try:
			self.spaceGroup
		except attributeError:
			self.runLog.writeToLog('Unable to find space group from file: {}'.format(self.PDBCURoutputFile))
			return False
		return True

	def mapConsistencyCheck(self,sfallMap,fftMap):
		# this function determines whether the atom map and density map calculated using SFALL and FFT
		# are compatible - meaning the grid dimensions/filtering are the same and the ordering of the
		# fast, medium, and slow axes are identical.
		self.runLog.writeToLog('Checking that atom map (SFALL) and density map (FFT) are compatible...')

		if (sfallMap.gridsamp1 != fftMap.gridsamp1 or
			sfallMap.gridsamp2 != fftMap.gridsamp2 or
			sfallMap.gridsamp3 != fftMap.gridsamp3):
			self.runLog.writeToLog('Incompatible grid sampling found...')
			return False

		if (sfallMap.fastaxis != fftMap.fastaxis or
			sfallMap.medaxis != fftMap.medaxis or
			sfallMap.slowaxis != fftMap.slowaxis):
			self.runLog.writeToLog('Incompatible fast,med,slow axes ordering found...')
			return False

		if (sfallMap.numCols != fftMap.numCols or
			sfallMap.numRows != fftMap.numRows or
			sfallMap.numSecs != fftMap.numSecs):
			self.runLog.writeToLog('Incompatible number of rows, columns and sections...')
			return False

		if sfallMap.getMapSize() != fftMap.getMapSize():
			self.runLog.writeToLog('Incompatible map file sizes')
			return False

		self.runLog.writeToLog('---> success!')
		return True

