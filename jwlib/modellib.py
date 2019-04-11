import config
import copy
import random

import time

# CellCollective Model Lib

def PercentChance(pct):
    m = random.randint(1, 100)
    if m <= pct:
        return '1'
    else:
        return '0'

class IDManager:
    RegulatorID    = None
    ConditionID    = None
    SubConditionID = None
    
    @staticmethod
    def SetModel(model):
        IDManager.Model = model

        # set next regulator ID
        regmap = IDManager.Model['regulatorMap']

        maxval = 0
        for i in regmap.keys():
            maxval = max(maxval, int(i))
            
        IDManager.RegulatorID = maxval

        # set next condition ID
        condmap = IDManager.Model['conditionMap']

        maxval = 0
        for i in condmap.keys():
            maxval = max(maxval, int(i))

        IDManager.ConditionID = maxval

        # set next subcondition ID
        subcondmap = IDManager.Model['subConditionMap']

        maxval = 0
        for i in subcondmap.keys():
            maxval = max(maxval, int(i))

        IDManager.SubConditionID = maxval

        # Condition Species Map ID
        IDManager.CSMapID = 0
    
    @staticmethod
    def NextRegulatorId():
        assert IDManager.RegulatorID != None, "IDManager is not configured!"
        IDManager.RegulatorID += 1
        return IDManager.RegulatorID

    @staticmethod
    def NextConditionId():
        assert IDManager.ConditionID != None, "IDManager is not configured!"
        IDManager.ConditionID += 1
        return IDManager.ConditionID

    @staticmethod
    def NextSubConditionID():
        assert IDManager.SubConditionID != None, "IDManager is not configured!"
        IDManager.SubConditionID += 1
        return IDManager.SubConditionID

    @staticmethod
    def NextConditionSpeciesMapId():
        IDManager.CSMapID += 1
        return IDManager.CSMapID - 1

    @staticmethod
    def Reset():
        IDManager.RegulatorID = None
        IDManager.ConditionID = None
        IDManager.SubConditionID = None
        IDManager.CSMapID = None

class CCNode:
    def __init__(self, specId):
        self.__specId = specId
        
        self.__regs = []
        self.__regtospec = {}
        self.__reglist = []
        self.__dominance = {}
        self.__conditions = {}
        self.__subconds = {}

    def Conform(self, other):
        self.__regs = other.__regs
        self.__regtospec = other.__regtospec
        self.__reglist = other.__reglist
        self.__dominance = other.__dominance
        self.__conditions = other.__conditions
        self.__subconds = other.__subconds

    def __str__(self):
        return "Regulating Nodes: %s\nDominances: %s\nConditions: %s\nSubConditions: %s" % (', '.join([str(i) for i in self.__reglist]), str(self.__dominance),
                                                                                            str(self.__conditions), str(self.__subconds))

    def Duplicate(self):
        c = CCNode(self.__specId)
        c.__regs = copy.deepcopy(self.__regs)
        c.__regtospec = copy.deepcopy(self.__regtospec)
        c.__reglist = copy.deepcopy(self.__reglist)
        c.__dominance = copy.deepcopy(self.__dominance)
        c.__conditions = copy.deepcopy(self.__conditions)
        c.__subconds = copy.deepcopy(self.__subconds)
        return c

    def AppropriateNewData(self, model):
        for i in self.__regs:
            if not unicode(i[2]) in model['regulatorMap'].keys():
                model['regulatorMap'][unicode(i[2])] = { 'regulationType': i[0], 'conditionRelation': i[1].upper(), 'regulatorSpeciesId': i[3],
                                                         'speciesId': self.__specId }
        
    def AddPosReg(self, specId, regId, conditionRelation="or"):
        self.__regtospec[regId] = specId
        self.__regs.append(("POSITIVE", conditionRelation.lower(), regId, specId))
        if not specId in self.__reglist:
            self.__reglist.append(specId)
        
    def AddNegReg(self, specId, regId, conditionRelation="or"):
        self.__regtospec[regId] = specId
        self.__regs.append(("NEGATIVE", conditionRelation.lower(), regId, specId))
        if not specId in self.__reglist:
            self.__reglist.append(specId)

    def IsPosReg(self, specId):
        for i in self.__regs:
            if i[3] == specId and i[0] == "POSITIVE":
                return True
        return False

    def IsNegReg(self, specId):
        for i in self.__regs:
            if i[3] == specId and i[0] == "NEGATIVE":
                return True
        return False

    def RemoveReg(self, regId):
        conds = []
        for i in self.__conditions.get(regId, {}):
            self.RemoveCondition(i[0])

        index = -1
        for i in xrange(0, len(self.__regs)):
            reg = self.__regs[i]
            if reg[2] == regId:
                index = i

        if index == -1:
            raise ValueError("No regulator with id %d." % regId)
        isPos = self.__regs[index][0] == "POSITIVE"
        
        if isPos:
            if regId in self.__dominance.keys():
                del self.__dominance[regId]
        else:
            for i in self.__dominance.keys():
                if regId in self.__dominance[i]:
                    self.__dominance[i].remove(regId)
                    if len(self.__dominance[i]) == 0:
                        del self.__dominance[i]
                        
        del self.__regs[index]
        self.__update_reglist()

    def GetPosRegData(self):
        posregs = []
        for i in self.__regs:
            if i[0] == "POSITIVE" and not i in posregs:
                    posregs.append(i)
        return posregs

    def GetNegRegData(self):
        negregs = []
        for i in self.__regs:
            if i[0] == "NEGATIVE" and not i in negregs:
                negregs.append(i)
        return negregs

    def GetRegData(self, regId):
        return self.__regs.get(regId)

    def GetPosRegs(self):
        posregs = []
        for i in self.__regs:
            if i[0] == "POSITIVE" and not i[3] in posregs:
                    posregs.append(i[3])
        return posregs

    def GetNegRegs(self):
        negregs = []
        for i in self.__regs:
            if i[0] == "NEGATIVE" and not i[3] in negregs:
                negregs.append(i[3])
        return negregs

    def GetPosRegIds(self):
        posregs = []
        for i in self.__regs:
            if i[0] == "POSITIVE" and not i[2] in posregs:
                    posregs.append(i[2])
        return posregs

    def GetNegRegIds(self):
        negregs = []
        for i in self.__regs:
            if i[0] == "NEGATIVE" and not i[2] in negregs:
                negregs.append(i[2])
        return negregs

    def GetPosRegNames(self, specmap):
        gpr = self.GetPosRegs()
        prn = []
        for i in gpr:
            prn.append( specmap[unicode(i)]['name'] )
        return prn

    def GetNegRegNames(self, specmap):
        gnr = self.GetNegRegs()
        grn = []
        for i in gnr:
            grn.append( specmap[unicode(i)]['name'] )
        return grn

    def GetConditions(self, regId):
        return self.__conditions.get(regId, {})

    def GetSubConditions(self, condId):
        return self.__subconds.get(condId, {})

    def GetRegList(self):
        return self.__reglist

    # Condition Indices
    CONDITION_ID_IDX          = 0
    CONDITION_CSTR_IDX        = 1
    CONDITION_STATE_IDX       = 2
    CONDITION_SPECREL_IDX     = 3
    CONDITION_SUBCONDREL_IDX  = 4
    CONDITION_SPECLIST_IDX    = 5
    CONDITION_SUBCONDLIST_IDX = 6

    def SetConditionProperty(self, condId, idx, val):
        for i in self.__conditions.keys():
            clist = self.__conditions[i]
            for j in xrange(0, len(clist)):
                if clist[j][0] == condId:
                    self.__conditions[i][j][idx] = val
                    return

        self.__update_reglist()

    def GetConditionProperty(self, condId, idx):
        for i in self.__conditions.keys():
            clist = self.__conditions[i]
            for j in clist:
                if j[0] == condId:
                    return j[idx]
    
    def AddCondition(self, regId, condId, specBoolOp, subcondBoolOp, state, ctype, speclist, subcondlist):
        specBoolOp = specBoolOp.lower()
        subcondBoolOp = subcondBoolOp.lower()
        if ctype == "IF_WHEN":
            cstr = ""
        elif ctype == "UNLESS":
            cstr = "not "
        else:
            raise ValueError("Conditon type must be either IF_WHEN or UNLESS.")
        if not (state == "ON" or state == "OFF"):
            raise ValueError("State must be either ON or OFF.")
        if not (specBoolOp == "and" or specBoolOp == "or"):
            raise ValueError("Species boolean relation must be either 'and' or 'or'.")
        if not (subcondBoolOp == "and" or subcondBoolOp == "or"):
            raise ValueError("Subcondition boolean relation must be either 'and' or 'or'.")
        if not regId in self.__conditions.keys():
            self.__conditions[regId] = list()
        for i in speclist:
            if not i in self.__reglist:
                self.__reglist.append(i)
        self.__conditions[regId].append( [condId, cstr, state, specBoolOp, subcondBoolOp, speclist, subcondlist] )

    def __update_reglist(self):
        regs = []
        for i in self.__regs:
            if not i[3] in regs:
                regs.append(i[3])
        for specId in self.__conditions.keys():
            c = self.__conditions[specId]
            for spec in c:
                con_regs = spec[5]
                for con in con_regs:
                    if not con in regs:
                        regs.append(con)
        for specId in self.__subconds.keys():
            c = self.__subconds[specId]
            for spec in c:
                con_regs = spec[4]
                for con in con_regs:
                    if not con in regs:
                        regs.append(con)
        self.__reglist = regs

    def RemoveCondition(self, condId):
        if condId in self.__subconds.keys():
            del self.__subconds[condId]
        for i in self.__conditions.keys():
            for cond in xrange(0, len(self.__conditions[i])):
                if self.__conditions[i][cond][0] == condId:
                    del self.__conditions[i][cond]
                    if len(self.__conditions[i]) == 0:
                        del self.__conditions[i]
                    self.__update_reglist()
                    return

    # SubCondition Indices
    SUBCONDITION_ID_IDX          = 0
    SUBCONDITION_CSTR_IDX        = 1
    SUBCONDITION_STATE_IDX       = 2
    SUBCONDITION_SPECREL_IDX     = 3
    SUBCONDITION_SPECLIST_IDX   = 4

    def SetSubConditionProperty(self, subCondId, idx, val):
        for i in self.__subconds.keys():
            clist = self.__subconds[i]
            for j in xrange(0, len(clist)):
                if clist[j][0] == subCondId:
                    self.__subconds[i][j][idx] = val
                    return

        self.__update_reglist()

    def GetSubConditionProperty(self, subCondId, idx):
        for i in self.__subconds.keys():
            clist = self.__subconds[i]
            for j in clist:
                if j[0] == subCondId:
                    return j[idx]

    def AddSubCondition(self, condId, subcondId, specBoolOp, state, ctype, speclist):
        specBoolOp = specBoolOp.lower()
        if ctype == "IF_WHEN":
            cstr = ""
        elif ctype == "UNLESS":
            cstr = "not "
        else:
            raise ValueError("Conditon type must be either IF_WHEN or UNLESS.")
        if not (state == "ON" or state == "OFF"):
            raise ValueError("State must be either ON or OFF.")
        if not (specBoolOp == "and" or specBoolOp == "or"):
            raise ValueError("Species boolean relation must be either 'and' or 'or'.")
        if not condId in self.__subconds.keys():
            self.__subconds[condId] = list()
        for i in speclist:
            if not i in self.__reglist:
                self.__reglist.append(i)
        self.__subconds[condId].append( [subcondId, cstr, state, specBoolOp, speclist] )

    def RemoveSubCondition(self, subCondId):
        for i in self.__subconds.keys():
            for subcond in xrange(0, len(self.__subconds[i])):
                if self.__subconds[i][subcond][0] == subCondId:
                    del self.__subconds[i][subcond]
                    self.__update_reglist()
                    return

    def RemoveAllDominances(self, posreg):
        if posreg in self.__dominance.keys():
            del self.__dominance[posreg]

    def AddDominance(self, posreg, negreg):
        if not posreg in self.__dominance.keys():
            self.__dominance[posreg] = list()
        self.__dominance[posreg].append(negreg)

    def RemoveDominance(self, posreg, negreg):
        self.__dominance[posreg].remove(negreg)
        if self.__dominance[posreg] == []:
            del self.__dominance[posreg]

    def SetDominance(self, posreg, negreg, isDom):
        if isDom:
            if (not posreg in self.__dominance.keys()) or (posreg in self.__dominance.keys() and not negreg in self.__dominance[posreg]):
                self.AddDominance(posreg, negreg)
        else:
            if (posreg in self.__dominance.keys() and negreg in self.__dominance[posreg]):
                self.RemoveDominance(posreg, negreg)

    def GetDominances(self, negreg):
        dom = []
        for i in self.__dominance.keys():
            if negreg in self.__dominance[i]:
                dom.append(i)
        return dom

    def Dominances(self, negreg):
        dom = 0
        for i in self.__dominance.keys():
            if negreg in self.__dominance[i]:
                dom += 1
        return dom

    def __gensubcondbool(self, condid, relation):
        scs = self.__subconds.get(condid)
        if scs == None:
            return None
        scres = []
        for i in scs:
            ss = i[1] + "(%s)"
            srelation = i[3]
            if i[2] == "OFF":
                ss = i[1] + "not (%s)"
                if srelation == "and":
                    srelation = "or"
                else:
                    srelation = "and"
            scres.append((ss % (" " + srelation + " ").join(["regs[%d]" % self.__reglist.index(j) for j in i[4]])))
        return "(" + (" " + relation + " ").join(scres) + ")"

    def __gencondbool(self, regId, specId, relation, isDom = False):
        cs = self.__conditions.get(regId)
        if cs == None:
            return None
        cres = []
        rid = self.__reglist.index(specId)
        for i in cs:
            ss = i[1] + "(%s)"
            srelation = i[3]
            if i[2] == "OFF":
                ss = i[1] + "not (%s)"
                if srelation == "and":
                    srelation = "or"
                else:
                    srelation = "and"
            gscb = self.__gensubcondbool( i[0], i[4] )
            if gscb == None:
                gscb = ""
            else:
                gscb = " and " + gscb
            cres.append((ss % (" " + srelation + " ").join(["regs[%d]" % self.__reglist.index(j) for j in i[5]]) + gscb) + " ")
        prefix = "regs[%d] and " % rid if isDom else ""
        return "(" + prefix + (" " + relation + " ").join(cres) + ")"

    def GenerateBooleanExpression(self, specmap, debug=False):
        exps = []
        reg = 0
        for i in self.__regs:
            exp = ""
            if i[0] == "POSITIVE":
                # pos reg stuff
                exp = "(regs[%d])" % self.__reglist.index(i[3])
                if i[2] in self.__dominance.keys():
                    doms = []
                    for j in self.__dominance[i[2]]:
                        found = False
                        for dreg in self.__regs:
                            if dreg[2] == j:
                                specId = dreg[3]
                                condRel = dreg[1]
                                found = True
                        if not found:
                            raise RuntimeError("Internal Error - could not find a dominance regulator. This error should never occur.")
                        gcb = self.__gencondbool(j, specId, condRel, True)
                        if gcb != None:
                            doms.append(gcb)
                        else:
                            doms.append("(regs[%d])" % self.__reglist.index(self.__regtospec[j])) # TODO: regulator-to-species map
                    for dom in doms:
                        exp += " and not %s" % dom
                else:
                    exp = "regs[%d]" % self.__reglist.index(i[3])
                gcbe = self.__gencondbool( i[2], i[3], i[1] ) # this should work
                if gcbe == None:
                    gcbe = ""
                else:
                    gcbe = " and " + gcbe
                exp += gcbe
                exps.append("(" + exp + ")")
            reg += 1
        return (' or '.join(exps), self.__reglist)
        
class Node:
    def __init__(self, name, exp, reg, ccnode, nid):
        self.name = name
        self.regulators = reg
        self.ccnode = ccnode
        self.__len_reg = len(reg)

        self.speciesId = nid
        
        exec 'func = lambda regs: int(%s)' % exp
        self.__func = func

        if len(reg) <= 16:
            gentt = {}
            for i in xrange(0, 2**len(reg)):
                b = bin(i)[2:].zfill(len(reg))
                blist = [int(j) for j in b]
                gentt[b] = func(blist)

            self.truth_table = gentt
        else:
            self.truth_table = None

    def ConformToCCNode(self, ccnode, specmap):
        self.ccnode.Conform(ccnode)
        self.exp, self.regulators = self.ccnode.GenerateBooleanExpression(specmap, True)
        self.__len_reg = len(self.regulators)

        exp = self.exp
        reg = self.regulators

        exec 'func = lambda regs: int(%s)' % exp
        self.__func = func

        if len(reg) <= 16:
            gentt = {}
            for i in xrange(0, 2**len(reg)):
                b = bin(i)[2:].zfill(len(reg))
                blist = [int(j) for j in b]
                gentt[b] = func(blist)

            self.truth_table = gentt
        else:
            self.truth_table = None

    def GetCCNode(self):
        return self.ccnode

    def TotalRegulators(self):
        """TotalRegulators()
        Gets the number of regulators."""
        return self.__len_reg

    def TestCondition(self, bitstring):
        for i in bitstring:
            if i != '1' and i != '0':
                raise ValueError("Condition must be a bitstring!")
        if len(bitstring) != self.TotalRegulators():
            raise ValueError("Number of bits must equal number of regulators!")
        if bitstring == '':
            bitstring = '0'
        if self.truth_table != None:
            return self.truth_table[bitstring]
        else:
            blist = [int(j) for j in bitstring]
            return self.__func(blist)

    def GetFast(self):
        if self.truth_table != None:
            return (self.truth_table, self.regulators, self.speciesId)
        else:
            # We *have* to generate the really big truth table :(
            gentt = {}
            for i in xrange(0, 2**len(reg)):
                b = bin(i)[2:].zfill(len(reg))
                blist = [int(j) for j in b]
                gentt[b] = self.__func(blist)

            self.truth_table = gentt
            return (self.truth_table, self.regulators, self.speciesId)

class Simulation:
    def __init__(self, ext_reg_env, prot_env, mutation_set={}):
        """Simulation(ExternalRegulatorEnvironment, NodeEnvironment, MutationSet)
        - ExternalRegulatorEnvironment is a dictionary associating external
        regulators to an activity level (0-100).
        - NodeEnvironment is a dictionary associating protein names to their
        Node class counterparts
        - MutationSet is a dictionary associating protein names to a value which
        they will hold consistently rather than allow themselves to be controlled
        by their typical regulators."""
        self.__erv  = ext_reg_env
        self.__pe   = prot_env
        self.__mut  = mutation_set
        self.__ervk = self.__erv.keys()
        self.__mutk = self.__mut.keys()

        self.__protlist = self.__pe.values()

        env1 = self.__erv.copy()
        env1.update(self.__pe)

        self.__fek = env1.keys()
        
        self.__steps = 0
        
        self.__state = {}
        for i in self.__pe.keys():
            self.__state[int(i)] = self.__pe[i].TestCondition('0' * (self.__pe[i].TotalRegulators()))

    def GetExternalRegulators(self):
        return self.__erv.copy()

    def GetInternalComponents(self):
        internal = {}
        ek = self.__erv.keys()
        for i in self.__pe.keys():
            if not i in ek:
                internal[i] = self.__pe[i]
        return internal

    def GetEnvironment(self):
        return self.__pe.copy()

    # DEPRECATED
    def ModifyNode(self, prot_name, in_bitstring, newval):
        if self.__pe[prot_name].truth_table != None:
            self.__pe[prot_name].truth_table[in_bitstring] = newval

    def ResetSimulation(self):
        self.__steps = 0
        for i in self.__pe.keys():
            self.__state[i] = self.__pe[i].TestCondition('0' * (self.__pe[i].TotalRegulators()))

    def __gen_bitstring(self, reg, full_env, fek):
        try:
            return ''.join([str(full_env[i]) for i in reg])
        except Exception as e:
            raise e # DEBUG ONLY!
            raise ValueError('Model Incorrectly Setup.')

    def RunStep(self):
        ext_reg = {}
        for i in self.__ervk:
            ext_reg[int(i)] = PercentChance(self.__erv[i])
        nstate = self.__state.copy()
        nstate.update(ext_reg)
        for prot in self.__protlist:
            if not prot.speciesId in self.__mutk:
                bits = self.__gen_bitstring(prot.regulators, nstate, self.__fek)
                self.__state[prot.speciesId] = prot.TestCondition(bits)
            elif nstate[prot.speciesId] != self.__mut[prot.speciesId]:
                self.__state[prot.speciesId] = self.__mut[prot.speciesId]
        self.__steps += 1
        
    def GetState(self):
        """GetState() - Returns a copy of the state dictionary"""
        return self.__state.copy()
    def GetSteps(self):
        return self.__steps
    def GetValue(self, node):
        return self.__state[node]

# Fast Simulation
class FastSimulation:
    def __init__(self, ext_reg_env, ervk, prot_env, envk, mutation_set={}, mutsetk=[]):
        """Simulation(ExternalRegulatorEnvironment, NodeEnvironment, MutationSet)
        - ExternalRegulatorEnvironment is a dictionary associating external
        regulators to an activity level (0-100).
        - NodeEnvironment is a dictionary associating protein names to their
        Node class counterparts
        - MutationSet is a dictionary associating protein names to a value which
        they will hold consistently rather than allow themselves to be controlled
        by their typical regulators."""
        self.__erv  = ext_reg_env
        self.__pe   = prot_env
        self.__mut  = mutation_set
        self.__ervk = ervk
        self.__pek  = envk
        self.__mutk = mutsetk

        env1 = self.__erv.copy()
        env1.update(self.__pe)

        self.__fek = env1.keys()
        
        self.__steps = 0
        
        self.__state = {}
        self.__ext_reg = {}
        for i in self.__pek:
            k = '0' * (len(self.__pe[i][1]))
            if k == '':
                k = '0'
            self.__state[int(i)] = self.__pe[i][0][k]

    def GetEnvironment(self):
        return self.__pe.copy()

    def ResetSimulation(self):
        self.__steps = 0
        for i in self.__pek():
            self.__state[i] = self.__pe[i][0][('0' * (len(self.__pe[i][1])))]

    def __gen_bitstring(self, reg, full_env, fek):
        if len(reg)==0:
            return '0'
        try:
            return ''.join([str(full_env[int(i)]) for i in reg])
        except Exception as e:
            raise e # DEBUG ONLY!
            raise ValueError('Model Incorrectly Setup.')

    def RunStep(self):
        self.__ext_reg = {}
        for i in self.__ervk:
            self.__ext_reg[int(i)] = PercentChance(self.__erv[i])
        nstate = self.__state.copy()
        nstate.update(self.__ext_reg)
        for _prot in self.__pek:
            prot = self.__pe[_prot]
            if not prot[2] in self.__mutk:
                bits = self.__gen_bitstring(prot[1], nstate, self.__fek)
                self.__state[prot[2]] = prot[0][bits]
            elif nstate[prot[2]] != self.__mut[prot[2]]:
                self.__state[prot[2]] = self.__mut[prot[2]]
        self.__steps += 1
        
    def GetState(self):
        """GetState() - Returns a copy of the state dictionary"""
        return self.__state.copy()
    def GetFullState(self):
        """GetFullState() - Returns a copy of the state dictionary, including external components"""
        s = self.GetState()
        s.update( self.__ext_reg )
        return s   
    def GetSteps(self):
        return self.__steps
    def GetValue(self, node):
        return self.__state[node]

class SimulationConfig:
    def __init__(self, ext_reg, env, mutations):
        self.ExternalRegulators = ext_reg
        self.InternalEnvironment = env
        self.MutationSet = mutations
