class ApgUser {
  final int id;
  final String name;
  final String email;
  final String role;

  const ApgUser({
    required this.id,
    required this.name,
    required this.email,
    required this.role,
  });

  bool get isAdmin => role.toLowerCase() == 'admin';

  factory ApgUser.fromJson(Map<String, dynamic> json) {
    return ApgUser(
      id: _readInt(json['id']),
      name: (json['name'] ?? 'APG').toString(),
      email: (json['email'] ?? '').toString(),
      role: (json['role'] ?? 'user').toString().toLowerCase(),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'email': email,
    'role': role,
  };
}

int _readInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.round();
  return int.tryParse('$value') ?? 0;
}
