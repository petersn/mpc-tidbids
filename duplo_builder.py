#!/usr/bin/python

# ===== basic circuit construction framework =====

class Gate:
	def __init__(self, operation, input_wires, output_wire):
		self.operation = operation
		self.input_wires = input_wires
		self.output_wire = output_wire

	def build(self, wire_num):
		inputs  = " ".join(str(wire_num(w)) for w in self.input_wires)
		outputs = str(wire_num(self.output_wire))
		return "%i %i %s %s %s" % (len(self.input_wires), 1, inputs, outputs, self.operation)

class Component:
	def __init__(self, circuit, *inputs):
		assert isinstance(circuit, Circuit), "First argument to a Component must be a Circuit!"
		self.circuit = circuit
		self.inputs = map(circuit.convert_to_wires, inputs)
		# Make sure out input ended up being the right size.
		assert len(self.inputs) == len(self.input_sizes), "Wrong number of inputs to component!"
		assert all(len(inp) == inp_size for inp, inp_size in zip(self.inputs, self.input_sizes)), "Bad input length!"
		self.output = [circuit.get_wire() for _ in xrange(self.output_size)]
		self.produce_gates()

	def produce_gates(self):
		raise NotImplementedError

class Circuit:
	class Wire:
		pass

	def __init__(self):
		self.wires = set()
		self.wires_by_name = {}
		self.gates = []

	def add_gate(self, gate):
		assert isinstance(gate, Gate), "Type error on add_gate!"
		self.gates.append(gate)

	def get_wire(self, name=None):
		if name != None:
			if name not in self.wires_by_name:
				self.wires_by_name[name] = self.get_wire()
			return self.wires_by_name[name]
		wire = Circuit.Wire()
		self.wires.add(wire)
		return wire

	@staticmethod
	def expand_name(name):
		if "::" in name:
			prefix, size = name.rsplit("::", 1)
			size = int(size)
			return ["%s_%i" % (prefix, i) for i in xrange(size)]
		return [name]

	def convert_to_wires(self, spec):
		if isinstance(spec, Circuit.Wire):
			return [spec]
		elif isinstance(spec, str):
			return [self.get_wire(name) for name in Circuit.expand_name(spec)]
		elif isinstance(spec, list):
			return sum(map(self.convert_to_wires, spec), [])
		elif isinstance(spec, Component):
			return self.convert_to_wires(spec.output)
		raise ValueError("Bad spec: %r" % (spec,))

	def build_description(self, left_inputs, right_inputs, outputs):
		left_input_wires  = self.convert_to_wires(left_inputs)
		right_input_wires = self.convert_to_wires(right_inputs)
		output_wires      = self.convert_to_wires(outputs)
		# We now format the contents.
		# Start by assigning wire numbers.
		wire_numbers = {}

		# Assign wire numbers as needed.
		counter = [0]
		def wire_num(w):
			assert w in self.wires
			if w not in wire_numbers:
				wire_numbers[w] = counter[0]
				counter[0] += 1
			return wire_numbers[w]

		for i, w in enumerate(left_input_wires):
			wire_num(w)
		for i, w in enumerate(right_input_wires):
			wire_num(w)
		for i, w in enumerate(output_wires):
			wire_numbers[w] = len(self.wires) - len(output_wires) + i

		contents = "\n".join(gate.build(wire_num) for gate in self.gates)
#		for name, w in self.wires_by_name.iteritems():
#			print "    %s: %i" % (name, wire_num(w))

		return "%i %i\n%i %i %i\n\n%s\n" % (
			len(self.gates),
			len(self.wires),
			len(left_input_wires),
			len(right_input_wires),
			len(output_wires),
			contents,
		)

	def save(self, path, *args):
		description = self.build_description(*args)
		with open(path, "w") as f:
			f.write(description)

# ===== functional circuits framework =====

class PrimitiveGate(Component):
	input_sizes = [1, 1]
	output_size = 1

	def produce_gates(self):
		self.circuit.add_gate(Gate(self.operation, [i[0] for i in self.inputs], self.output[0]))

class ANDGate(PrimitiveGate):
	operation = "AND"

class XORGate(PrimitiveGate):
	operation = "XOR"

class INVGate(PrimitiveGate):
	input_sizes = [1]
	operation = "INV"

class Subcircuit(Component):
	def __init__(self, parent, *args):
		self.parent = parent
		self.input_sizes = [parent.left_input_wire_count, parent.right_input_wire_count]
		self.output_size = parent.output_wire_count
		Component.__init__(self, *args)

	def produce_gates(self):
		parent = self.parent
		# First, produce a mapping of the string wire names that occur in parent.gate_descriptions into actual wires of our circuit.
		name_to_wire = {}
		for i, w in enumerate(self.inputs[0]):
			name_to_wire[str(i)] = w
		for i, w in enumerate(self.inputs[1]):
			name_to_wire[str(parent.left_input_wire_count + i)] = w
		for i, w in enumerate(self.output):
			name_to_wire[str(parent.wire_count - len(self.output) + i)] = w
		def get_wire(name):
			if name not in name_to_wire:
				name_to_wire[name] = self.circuit.get_wire()
			return name_to_wire[name]
		for desc in parent.gate_descriptions:
			# Ignore the first two entries -- those are input count and output count.
			input_names = desc[2:-2]
			output_name = desc[-2]
			operation = desc[-1]
			self.circuit.add_gate(Gate(
				operation,
				map(get_wire, input_names),
				get_wire(output_name),
			))

class BristolCircuit:
	def __init__(self, path):
		with open(path) as f:
			get_fields = lambda: map(int, f.readline().split())
			self.gate_count, self.wire_count = get_fields()
			self.left_input_wire_count, self.right_input_wire_count, self.output_wire_count = get_fields()
			self.gate_descriptions = [l.split() for l in f.readlines() if l.strip()]
		assert len(self.gate_descriptions) == self.gate_count, "Bad gate count. Expected %i, got %i." % (self.gate_count, len(self.gate_descriptions))
		print "Read %i x %i -> %i with %i gates from: %s" % (self.left_input_wire_count, self.right_input_wire_count, self.output_wire_count, self.gate_count, path)

	def __call__(self, circuit, *inputs):
		return Subcircuit(self, circuit, *inputs)

if __name__ == "__main__":
#	aes = BristolCircuit("AES-non-expanded.txt")
#	simp = BristolCircuit("simple.txt")
	c = Circuit()
#	z = simp(c, "l::2", "r::2")
#	foo = simp(c, z, "l::2")
#	y = aes(c, "i_0::128", "i_1::128")
	x = ANDGate(c, "l_0", "l_1")
	y = ANDGate(c, "r_0", "r_1")
	z1 = XORGate(c, x, y)
	z2 = ANDGate(c, x, y)
	t = c.build_description("l::2", "r::2", [z1, z2])
	print t.strip()

