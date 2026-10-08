# Uso basico de Cassandra (creación de Keyspace, Tablas,Inserciones y Consultas)

**Cosas a tener en cuenta sobre cql:**
    
    - A pesar de parecerse enormemente a sql, tiene limitaciones muy importantes
    - No existen relaciones en las tablas, así que información que deba estar en varias tablas sera replicada e lugar de enlazada.
    - Hay que definir el orden de muestra de los datos a la hora de crear la propia tabla, y tras esto no pueden ordenarse de otra manera.
    - Solo se puede filtrar en consultas de forma eficiente por elementos de la clave primaria
    - En los filtros de las consultas, los elementos de la pk siempre deben ir en orden y su orden no se puede alterar. Si en la tabla los elementos de la pk se declararon por ejemplo como ((A),B,C), solo se podrá visualizar en ese orden.
    - En un filtro, la key principal ("clave de partición") de la pk siempre debe estar presente con un operador de igualdad (=).
    - Regla del "salto de columnas": No puedes saltarte el orden físico de los elementos de la pk en el filtro. Siguiendo el ejemplo ((A), B, C), puedes filtrar por A, o por A y B, o por A, B y C. Sin embargo, jamás podrás filtrar por A y C sin incluir a B en medio.


En Cassandra, la base de datos se denomina **keyspace**. Los permisos sobre el keyspace los concede un administrador.

> Esta guiá retoma desde el final de la guiá de instalación de Cassandra, por lo que los usuarios son los mismos que creamos en la instalación.

## 1. Creación del Keyspace y Asignación de Permisos

Con el usuario administrador, creamos el keyspace `ks_prueba` y concedemos todos los permisos sobre él al usuario normal:

```
cqlsh TU_IP_SERVIDOR -u cassandraadmin -p '<PASSWORD_ADMIN>' << 'EOF'
CREATE KEYSPACE ks_prueba WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};
GRANT ALL PERMISSIONS ON KEYSPACE ks_prueba TO usuario_prueba;
EOF
```

> `SimpleStrategy` con factor de replicación 1 es válido para este entorno de ejemplo ya que solo tenemos un nodo. En un clúster real usaríamos `NetworkTopologyStrategy` con el factor de replicación adecuado.

Comprobamos el keyspace y los permisos concedidos:

```
cqlsh TU_IP_SERVIDOR -u cassandraadmin -e "DESCRIBE KEYSPACE ks_prueba;"
cqlsh TU_IP_SERVIDOR -u cassandraadmin -e "LIST ALL PERMISSIONS OF usuario_prueba;"
```

```
debian@cliente:~$ cqlsh 192.168.122.91 -u cassandraadmin -e "DESCRIBE KEYSPACE ks_prueba;"
Password:
WARNING: cqlsh was built against 5.0.0, but this server is 5.0.9.  All features may not work!

CREATE KEYSPACE ks_prueba WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'}  AND durable_writes = true;

debian@cliente:~$ cqlsh 192.168.122.91 -u cassandraadmin -e "LIST ALL PERMISSIONS OF usuario_prueba;"Password:
WARNING: cqlsh was built against 5.0.0, but this server is 5.0.9.  All features may not work!

 role           | username       | resource             | permission
----------------+----------------+----------------------+---------------
 usuario_prueba | usuario_prueba | <keyspace ks_prueba> |        CREATE
 usuario_prueba | usuario_prueba | <keyspace ks_prueba> |         ALTER
 usuario_prueba | usuario_prueba | <keyspace ks_prueba> |          DROP
 usuario_prueba | usuario_prueba | <keyspace ks_prueba> |        SELECT
 usuario_prueba | usuario_prueba | <keyspace ks_prueba> |        MODIFY
 usuario_prueba | usuario_prueba | <keyspace ks_prueba> |     AUTHORIZE
 usuario_prueba | usuario_prueba | <keyspace ks_prueba> |        UNMASK
 usuario_prueba | usuario_prueba | <keyspace ks_prueba> | SELECT_MASKED

(8 rows)
```

## 2. Creación de una Tabla

Desde el cliente remoto, nos conectamos con el usuario de aplicación indicando el keyspace y creamos la tabla `clientes`. La clave primaria (`id`) identifica cada fila:

```
cqlsh TU_IP_SERVIDOR 9042 -u usuario_prueba -k ks_prueba
```

```
CREATE TABLE clientes (
  id int PRIMARY KEY,
  nombre text,
  email text,
  edad int,
  activo boolean,
  fecha_registro timestamp
);
```

Comprobamos la estructura de la tabla creada:

```
DESCRIBE TABLE clientes;
```

```
usuario_prueba@cqlsh:ks_prueba> DESCRIBE TABLE clientes;

CREATE TABLE ks_prueba.clientes (
    id int PRIMARY KEY,
    activo boolean,
    edad int,
    email text,
    fecha_registro timestamp,
    nombre text
) WITH additional_write_policy = '99p'
    AND allow_auto_snapshot = true
    AND bloom_filter_fp_chance = 0.01
    AND caching = {'keys': 'ALL', 'rows_per_partition': 'NONE'}
    AND cdc = false
    AND comment = ''
    AND compaction = {'class': 'org.apache.cassandra.db.compaction.SizeTieredCompactionStrategy', 'max_threshold': '32', 'min_threshold': '4'}
    AND compression = {'chunk_length_in_kb': '16', 'class': 'org.apache.cassandra.io.compress.LZ4Compressor'}
    AND memtable = 'default'
    AND crc_check_chance = 1.0
    AND default_time_to_live = 0
    AND extensions = {}
    AND gc_grace_seconds = 864000
    AND incremental_backups = true
    AND max_index_interval = 2048
    AND memtable_flush_period_in_ms = 0
    AND min_index_interval = 128
    AND read_repair = 'BLOCKING'
    AND speculative_retry = '99p';
```

## 3. Introducción de Información (Inserción)

Insertamos filas en la tabla `clientes`. CQL no dispone de una sentencia de inserción múltiple en una sola instrucción, por lo que se ejecuta un `INSERT` por fila:

- **Insertar una fila:**

```
INSERT INTO clientes (id, nombre, email, edad, activo, fecha_registro)
VALUES (1, 'Juan Pérez', 'juan.perez@example.com', 30, true, toTimestamp(now()));
```

- **Insertar más filas:**

```
INSERT INTO clientes (id, nombre, email, edad, activo) VALUES (2, 'Ana Gómez', 'ana.gomez@example.com', 25, true);
INSERT INTO clientes (id, nombre, email, edad, activo) VALUES (3, 'Carlos Ruiz', 'carlos.ruiz@example.com', 40, false);
```

## 4. Consulta de Información (Lectura)

Ahora realizaremos un par de consultas para familiarizarnos con el motor:

- **Consultar todas las filas de una tabla:**

```
SELECT * FROM clientes;
```

```
usuario_prueba@cqlsh:ks_prueba> SELECT * FROM clientes;
[INSERTA AQUÍ LA SALIDA DEL COMANDO EN TU TERMINAL]
```

* **Consultar por clave primaria:**

```
SELECT * FROM clientes WHERE id = 1;
```

```
usuario_prueba@cqlsh:ks_prueba> SELECT * FROM clientes;

 id | activo | edad | email                   | fecha_registro                  | nombre
----+--------+------+-------------------------+---------------------------------+-------------
  1 |   True |   30 |  juan.perez@example.com | 2026-10-08 19:18:48.973000+0000 |  Juan Pérez
  2 |   True |   25 |   ana.gomez@example.com |                            null |   Ana Gómez
  3 |  False |   40 | carlos.ruiz@example.com |                            null | Carlos Ruiz

(3 rows)
```

* **Consultar con filtros sobre columnas que no son clave:**

Cassandra solo permite filtrar de forma eficiente por columnas que pertenecen a la clave primaria. Para filtrar por otras columnas se añade `ALLOW FILTERING`, aceptable en pruebas con pocos datos pero no recomendable en tablas grandes, donde la practica es diseñar tablas o índices específicos para cada consulta.

```
-- Obtener los clientes que estén activos
SELECT * FROM clientes WHERE activo = true ALLOW FILTERING;
```

```
usuario_prueba@cqlsh:ks_prueba> SELECT * FROM clientes WHERE activo = true ALLOW FILTERING;

 id | activo | edad | email                  | fecha_registro                  | nombre
----+--------+------+------------------------+---------------------------------+------------
  1 |   True |   30 | juan.perez@example.com | 2026-10-08 19:18:48.973000+0000 | Juan Pérez
  2 |   True |   25 |  ana.gomez@example.com |                            null |  Ana Gómez

(2 rows)
```

```
-- Obtener los clientes con edad mayor a 28 años
SELECT * FROM clientes WHERE edad > 28 ALLOW FILTERING;
```

```
usuario_prueba@cqlsh:ks_prueba> SELECT * FROM clientes WHERE edad > 28 ALLOW FILTERING;

 id | activo | edad | email                   | fecha_registro                  | nombre
----+--------+------+-------------------------+---------------------------------+-------------
  1 |   True |   30 |  juan.perez@example.com | 2026-10-08 19:18:48.973000+0000 |  Juan Pérez
  3 |  False |   40 | carlos.ruiz@example.com |                            null | Carlos Ruiz

(2 rows)
```

**Consulta con orden de datos**

Cassandra no permite ordenar la salida de las consultas de otra forma que sea en la que estan en disco, es decir, como salen en consultas normales. Si tratamos de hacerlo, solo recibiremos un error:

```
SELECT * FROM clientes ORDER BY edad DESC;
```

```
usuario_prueba@cqlsh:ks_prueba> SELECT * FROM clientes ORDER BY edad DESC;
InvalidRequest: Error from server: code=2200 [Invalid query] message="ORDER BY is only supported when the partition key is restricted by an EQ or an IN."
```

Es por ello que si queremos que las consultas estén ordenadas de una forma por uno o varios campos, este orden hay que aplicarlo a la propia tabla a la hora que crearla usando la sentencia WITH CLUSTERING, como podemos ver en el siguiente ejemplo:

```
CREATE TABLE clientes (
  activo boolean,
  edad int,
  id int,
  nombre text,
  email text,
  fecha_registro timestamp,
  PRIMARY KEY ((activo), edad)
) WITH CLUSTERING ORDER BY (edad DESC);
```