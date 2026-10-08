# Guía de Instalación, Configuración y Uso Básico de MongoDB (servidor) y Mongosh(cliente) en Debian 13 (Por Alfredo)

Esta guía cubre el procedimiento completo de instalación de MongoDB Community y `mongosh` (cliente), la activación de la autenticación, la configuración de acceso remoto, la gestión básica de usuarios y las operaciones de creación de bases de datos, inserción y consulta de datos.

> **Valores de ejemplo empleados:**
>
> * **IP del Servidor**: `TU_IP_SERVIDOR`
>
> * **Red de los Clientes**: `TU_RED_CLIENTE` (ejemplo: `192.168.122.0/24`)
>
> * **Base de Datos**: `bd-prueba`
>
> * **Usuario Administrador**: `mongoadmin`
>
> * **Usuario de Aplicación**: `usuario-prueba`

## 1. Servidor: Instalación de MongoDB y Configuración Inicial

### 1.1. Añadir el Repositorio Oficial e Instalar Paquetes

Importamos la clave GPG del repositorio oficial e instalamos la suite de MongoDB (`mongodb-org`):

```
sudo apt update
sudo apt install -y gnupg curl

curl -fsSL https://pgp.mongodb.com/server-8.0.asc | \
sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor

echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] http://repo.mongodb.org/apt/debian bookworm/mongodb-org/8.0 main" | \
sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list

sudo apt update
sudo apt install -y mongodb-org
```

### 1.2. Arranque del Servicio

Iniciamos y habilitamos el servicio `mongod`:

```
sudo systemctl enable --now mongod
sudo systemctl status mongod --no-pager
```

```
debian@mongodb:~$ sudo systemctl status mongod --no-pager
● mongod.service - MongoDB Database Server
     Loaded: loaded (/usr/lib/systemd/system/mongod.service; enabled; preset: enabled)
     Active: active (running) since Wed 2026-10-07 13:46:02 UTC; 27ms ago
 Invocation: d27328680d414748b1652e8ce650e516
       Docs: https://docs.mongodb.org/manual
   Main PID: 1465 (mongod)
     Memory: 1.5M (peak: 2M)
        CPU: 8ms
     CGroup: /system.slice/mongod.service
             └─1465 /usr/bin/mongod --config /etc/mongod.conf
```

Comprobamos la versión del servidor instalada:

```
mongod --version
```

```
debian@mongodb:~$ mongod --version
db version v8.0.32
Build Info: {
    "version": "8.0.32",
    "gitVersion": "f9eb55a7cc900f33a722a5b32a0fdbf54385c749",
    "openSSLVersion": "OpenSSL 3.5.7 9 Jun 2026",
    "modules": [],
    "allocator": "tcmalloc-google",
    "environment": {
        "distmod": "debian12",
        "distarch": "x86_64",
        "target_arch": "x86_64"
    }
}
```

## 2. Servidor: Gestión Básica de Usuarios y Habilitación de Autenticación

Por defecto, MongoDB escucha únicamente en `127.0.0.1` y no requiere autenticación. En este paso se crean los usuarios antes de abrir el servicio a la red.

### 2.1. Creación de Usuarios Administrador y de Aplicación

Conectamos localmente e introducimos los usuarios en sus respectivas bases de datos (`authSource`):

```
mongosh --quiet << 'EOF'
db.getSiblingDB("admin").createUser({
  user: "mongoadmin",
  pwd: "<PASSWORD_ADMIN>",
  roles: [ { role: "root", db: "admin" } ]
})
db.getSiblingDB("bd-prueba").createUser({
  user: "usuario-prueba",
  pwd: "<PASSWORD_APP>",
  roles: [ { role: "readWrite", db: "bd-prueba" } ]
})
EOF
```

### 2.2. Habilitar Autenticación y Acceso Remoto

Editamos `/etc/mongod.conf` para exigir autenticación (`authorization: enabled`) y vincular la IP del servidor(muy importante, a ip del servidor mongo, no la del cliente) a las interfaces de escucha:

```
sudo tee -a /etc/mongod.conf << 'EOF'

security:
  authorization: enabled
EOF

sudo sed -i 's/^  bindIp: .*/  bindIp: 127.0.0.1,TU_IP_SERVIDOR/' /etc/mongod.conf
sudo systemctl restart mongod
```

Verificamos la configuración y la escucha en la red por el puerto 27017:

```
grep -A3 -E '^(net|security):' /etc/mongod.conf
sudo ss -tlnp | grep 27017
```

```
debian@mongodb:~$ grep -A3 -E '^(net|security):' /etc/mongod.conf
net:
  port: 27017
  bindIp: 127.0.0.1,TU_IP_SERVIDOR

--
security:
  authorization: enabled
  
debian@mongodb:~$ sudo ss -tlnp | grep 27017
LISTEN 0      4096       127.0.0.1:27017      0.0.0.0:*    users:(("mongod",pid=1564,fd=9))
```

Comprobamos que ya no se permite operar sin autenticación desde el propio servidor:

```
mongosh --quiet --eval 'db.getSiblingDB("bd-prueba").getCollectionNames()'
```

```
debian@mongodb:~$ mongosh --quiet --eval 'db.getSiblingDB("bd-prueba").getCollectionNames()'
MongoServerError: Command listCollections requires authentication
```

## 3. Cliente: Instalación y Conexión del Cliente Remoto

En el equipo cliente se instala únicamente la shell oficial de MongoDB (`mongosh`) sin instalar el motor de base de datos.

### 3.1. Instalación de `mongosh` en el Cliente Remoto

```
sudo apt update
sudo apt install -y gnupg curl

curl -fsSL https://pgp.mongodb.com/server-8.0.asc | \
sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor

echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] http://repo.mongodb.org/apt/debian bookworm/mongodb-org/8.0 main" | \
sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list

sudo apt update
sudo apt install -y mongodb-mongosh
```

### 3.2. Conexión Remota al Servidor

Nos conectamos desde la máquina cliente hacia la base de datos remota utilizando el usuario autenticado:

```
mongosh "mongodb://TU_IP_SERVIDOR:27017/bd-prueba?authSource=bd-prueba" -u usuario-prueba
```

Una vez dentro de la shell, podemos verificar el estado de la conexión y ver que usamos el usuario correcto:

```
db.runCommand({ connectionStatus: 1 })
```

```
bd-prueba> db.runCommand({ connectionStatus: 1 })
{
  authInfo: {
    authenticatedUsers: [ { user: 'usuario-prueba', db: 'bd-prueba' } ],
    authenticatedUserRoles: [ { role: 'readWrite', db: 'bd-prueba' } ]
  },
  ok: 1
}
```

## 4. Creación de Bases de Datos, Introducción y Ejemplos de Uso Basico.

Una vez conectados con el servidor, podemos probar la base insertando datos en una colección y haciendo consultas. En MongoDB, las bases de datos y las colecciones se crean implícitamente al insertar el primer documento.

### 4.1. Introducción de Información (Inserción)

Insertamos documentos en una colección denominada `clientes`:

* **Insertar un único documento (`insertOne`):**

```
db.clientes.insertOne({
  nombre: "Juan Pérez",
  email: "juan.perez@example.com",
  edad: 30,
  activo: true,
  fechaRegistro: new Date()
})
```

```
bd-prueba> db.clientes.insertOne({
|   nombre: "Juan Pérez",
|   email: "juan.perez@example.com",
|   edad: 30,
|   activo: true,
|   fechaRegistro: new Date()
| })
{
  acknowledged: true,
  insertedId: ObjectId('6ac6512ed9261a7b7ca92131')
}
```

* **Insertar múltiples documentos (`insertMany`):**

```
db.clientes.insertMany([
  { nombre: "Ana Gómez", email: "ana.gomez@example.com", edad: 25, activo: true },
  { nombre: "Carlos Ruiz", email: "carlos.ruiz@example.com", edad: 40, activo: false }
])
```

```
bd-prueba> db.clientes.insertMany([
|   { nombre: "Ana Gómez", email: "ana.gomez@example.com", edad: 25, activo: true },
|   { nombre: "Carlos Ruiz", email: "carlos.ruiz@example.com", edad: 40, activo: false }
| ])
{
  acknowledged: true,
  insertedIds: {
    '0': ObjectId('6ac6514fd9261a7b7ca92132'),
    '1': ObjectId('6ac6514fd9261a7b7ca92133')
  }
}
```

### 4.2. Consulta de Información (Lectura)

Ahora realizaremos un par de consultas para familiarizarnos con el motor:

* **Consultar todos los documentos de una colección:**
```
db.clientes.find()
```

```
bd-prueba> db.clientes.find()
[
  {
    _id: ObjectId('6ac6512ed9261a7b7ca92131'),
    nombre: 'Juan Pérez',
    email: 'juan.perez@example.com',
    edad: 30,
    activo: true,
    fechaRegistro: ISODate('2026-10-07T14:03:26.587Z')
  },
  {
    _id: ObjectId('6ac6514fd9261a7b7ca92132'),
    nombre: 'Ana Gómez',
    email: 'ana.gomez@example.com',
    edad: 25,
    activo: true
  },
  {
    _id: ObjectId('6ac6514fd9261a7b7ca92133'),
    nombre: 'Carlos Ruiz',
    email: 'carlos.ruiz@example.com',
    edad: 40,
    activo: false
  }
]
```

* **Consultar con filtros:**

```
// Obtener los clientes que estén activos
db.clientes.find({ activo: true })
```

```
bd-prueba> db.clientes.find({ activo: true })
[
  {
    _id: ObjectId('6ac6512ed9261a7b7ca92131'),
    nombre: 'Juan Pérez',
    email: 'juan.perez@example.com',
    edad: 30,
    activo: true,
    fechaRegistro: ISODate('2026-10-07T14:03:26.587Z')
  },
  {
    _id: ObjectId('6ac6514fd9261a7b7ca92132'),
    nombre: 'Ana Gómez',
    email: 'ana.gomez@example.com',
    edad: 25,
    activo: true
  }
]
```

```
// Obtener los clientes con edad mayor a 28 años
db.clientes.find({ edad: { $gt: 28 } })
```

```
bd-prueba> db.clientes.find({ edad: { $gt: 28 } })
[
  {
    _id: ObjectId('6ac6512ed9261a7b7ca92131'),
    nombre: 'Juan Pérez',
    email: 'juan.perez@example.com',
    edad: 30,
    activo: true,
    fechaRegistro: ISODate('2026-10-07T14:03:26.587Z')
  },
  {
    _id: ObjectId('6ac6514fd9261a7b7ca92133'),
    nombre: 'Carlos Ruiz',
    email: 'carlos.ruiz@example.com',
    edad: 40,
    activo: false
  }
]
```

* **Proyección (seleccionar solo campos específicos):**

```
// Mostrar únicamente el nombre y el email
db.clientes.find({}, { nombre: 1, email: 1, _id: 0 })
```

```
bd-prueba> db.clientes.find({}, { nombre: 1, email: 1, _id: 0 })
[
  { nombre: 'Juan Pérez', email: 'juan.perez@example.com' },
  { nombre: 'Ana Gómez', email: 'ana.gomez@example.com' },
  { nombre: 'Carlos Ruiz', email: 'carlos.ruiz@example.com' }
]
```







