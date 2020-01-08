"""exporter.py: abstract classes for exporting facts"""

import abc
import csv
import logging
import os
from collections import defaultdict
import src.opcodes as opcodes
from src.common import public_function_signature_filename, event_signature_filename


opcode_output = {'alters_flow':bool, 'halts':bool, 'is_arithmetic':bool,
                 'is_call':bool, 'is_dup':bool, 'is_invalid':bool,
                 'is_log':bool, 'is_memory':bool, 'is_missing':bool,
                 'is_push':bool, 'is_storage':bool, 'is_swap':bool,
                 'log_len':int, 'possibly_halts':bool, 'push_len':int,
                 'stack_delta':int, 'pop_words':int, 'push_words':int,
                 'gas': int, 'ord':int
}    

def generate_interface():
    f = open('logic/decompiler_input_statements.dl', 'w')
    f.write('// Fact loader. This file was generated by bin/generatefacts, do not edit\n\n')
    
    for opname, opcode in opcodes.OPCODES.items():
        if opcode.is_push():
            f.write(f'.decl {opname}(stmt: Statement, value: Value)\n')
            f.write(f'{opname}(stmt, value) :- Statement_Opcode(stmt, "{opname}"), PushValue(stmt, value).\n')
        else:
            f.write(f'.decl {opname}(stmt: Statement)\n')
            f.write(f'{opname}(stmt) :- Statement_Opcode(stmt, "{opname}").\n')
        f.write('\n')
    f.close()
    f = open('logic/decompiler_input_opcodes.dl', 'w')
    f.write('// Static opcode data. This file was generated by bin/generatefacts, do not edit\n\n')
    for prop, typ in opcode_output.items():
        relname = ''.join(map(lambda a : a[0].upper()+ a[1:], ('opcode_'+prop).split('_')))
        if typ == bool:
            f.write(f'.decl {relname}(instruction: Opcode)\n')
            f.write(f'{relname}(instruction) :- {relname}(instruction).\n')
        elif typ == int:
            f.write(f'.decl {relname}(instruction: Opcode, n: number)\n')
            f.write(f'{relname}(instruction, n) :- {relname}(instruction, n).\n')
        else:
            raise NotImplementedError('Unknown: '+str(typ))
      
        f.write('\n')

    opcode_key = 'name'
    for prop, typ in opcode_output.items():
        relname = ''.join(map(lambda a : a[0].upper()+ a[1:], ('opcode_'+prop).split('_')))
        opcode_property = []
        for k, opcode in opcodes.OPCODES.items():
            prop_val = getattr(opcode, prop)()
            if typ == bool and prop_val:
                f.write(f'{relname}("{getattr(opcode, opcode_key)}").\n')
            elif typ == int:
                f.write(f'{relname}("{getattr(opcode, opcode_key)}", {prop_val}).\n')
        f.write('\n')
    f.close()

def get_disassembly(statement_opcode, push_value):
    output = []
    row_format ="{:>7}: {:<10}"
    for s, op in statement_opcode:
        row = row_format.format(s, op)
        if s in push_value:
            row += push_value[s]
        output.append(row)
    return '\n'.join(output)            


class Exporter(abc.ABC):
    def __init__(self, source: object):
        """
        Args:
          source: object instance to be exported
        """
        self.source = source

    @abc.abstractmethod
    def export(self):
        """
        Exports the source object to an implementation-specific format.
        """


class InstructionTsvExporter(Exporter):
    """
    Prints a textual representation of the given CFG to stdout.

    Args:
      cfg: source CFG to be printed.
      ordered: if True (default), print BasicBlocks in order of entry.
    """

    def __init__(self, blocks, ordered: bool = True):
        self.ordered = ordered
        self.blocks = []
        self.blocks = blocks

    def visit_ControlFlowGraph(self, cfg):
        """
        Visit the CFG root
        """
        pass

    def visit_BasicBlock(self, block):
        """
        Visit a BasicBlock in the CFG
        """
        self.blocks.append((block.entry, str(block)))
    
    def export(self, output_dir = ""):
        """
        Print basic block info to tsv.
        """
        if output_dir != "":
            os.makedirs(output_dir, exist_ok=True)

        signatures_filename_in = public_function_signature_filename
        signatures_filename_out = os.path.join(output_dir, 'PublicFunctionSignature.facts')
        if os.path.isfile(signatures_filename_in):
            try:
                os.symlink(signatures_filename_in, signatures_filename_out)
            except FileExistsError:
                pass
        else:
            open(signatures_filename_out, 'w').close()
            
        events_filename_in = event_signature_filename
        events_filename_out = os.path.join(output_dir, 'EventSignature.facts')
        if os.path.isfile(events_filename_in):
            try:
                os.symlink(events_filename_in, events_filename_out)
            except FileExistsError:
                pass
        else:
            open(events_filename_out, 'w').close()    

        def join(filename):
            return os.path.join(output_dir, filename)

        def generate(filename, entries):
            with open(join(filename), 'w') as f:
                writer = csv.writer(f, delimiter='\t', lineterminator='\n')
                writer.writerows(entries)


        instructions = []
        instructions_order = []
        push_value = []
        for block in self.blocks:
            for op in block.evm_ops:
                instructions_order.append(int(op.pc))
                instructions.append((hex(op.pc), op.opcode.name))
                if op.opcode.is_push():
                    push_value.append((hex(op.pc), hex(op.value)))

        instructions_order = list(map(hex, sorted(instructions_order)))
        generate('Statement_Next.facts', zip(instructions_order, instructions_order[1:]))

        generate('Statement_Opcode.facts', instructions)
                    
        generate('PushValue.facts', push_value)
        dasm = get_disassembly(instructions, dict(push_value))
        with open(join('contract.dasm'), 'w') as f:
            f.write(dasm)
        
        
