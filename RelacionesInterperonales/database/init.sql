CREATE TABLE vinculacion_afectiva (
    vinculacionAfectiva INT PRIMARY KEY,
    --confianzaInterpersonal VARCHAR(100),
    noviazgo BOOLEAN,
    tiempoSoltero INT CHECK (tiempoSoltero >= 0)
);

CREATE TABLE sociabilidad (
    perfilSocial INT PRIMARY KEY,
    habilidadSocial INT CHECK (habilidadSocial BETWEEN 1 AND 5),
    amigos BOOLEAN, -- 0 = No 1 = Si 
    energiaInterpersonal INT CHECK (energiaInterpersonal BETWEEN 1 AND 5) -- energiaInterpersonal
);

CREATE TABLE estilo_vida (
    estiloVida INT PRIMARY KEY,
    enfoque BOOLEAN,
    --tiempoLibre VARCHAR(100),
    trabaja BOOLEAN -- 0 = No 1 = Si 
);

CREATE TABLE colaboracion (
    colaboracion INT PRIMARY KEY,
    colaborativo BOOLEAN,
    integracion INT CHECK (integracion BETWEEN 1 AND 5),
    participacion INT CHECK (participacion BETWEEN 0 AND 2)
);

CREATE TABLE estilo_comunicacion (
    comunicacionInterpersonal INT PRIMARY KEY,
    comunicacion BOOLEAN,
    inciativaInteraccional VARCHAR(100)
);

CREATE TABLE relaciones_intepersonales (
    num_cuenta INT PRIMARY KEY,
    vinculacionAfectiva INT,
    perfilSocial INT,
    estiloVida INT,
    colaboracion INT,
    comunicacionIntepersonal INT,
    CONSTRAINT fk_vinculacion_afectiva
        FOREIGN KEY (vinculacionAfectiva)
        REFERENCES vinculacion_afectiva(vinculacionAfectiva),
    CONSTRAINT fk_sociabilidad
        FOREIGN KEY (perfilSocial)
        REFERENCES sociabilidad(perfilSocial),
    CONSTRAINT fk_estilo_vida
        FOREIGN KEY (estiloVida)
        REFERENCES estilo_vida(estiloVida),
    CONSTRAINT fk_colaboracion
        FOREIGN KEY (colaboracion)
        REFERENCES colaboracion(colaboracion),
    CONSTRAINT fk_estilo_comunicacion
        FOREIGN KEY (comunicacionIntepersonal)
        REFERENCES estilo_comunicacion(comunicacionInterpersonal)
);

CREATE TABLE caracteristicas_individuales(
    caracteristicas INT PRIMARY KEY,
    genero BOOLEAN, -- 1 = Hombre 2 = Mujer
    generacion INT,
    edad INT
);

CREATE TABLE mac (
    num_cuenta INT PRIMARY KEY,
    caracteristicas INT,
    estiloVida INT,
    CONSTRAINT fk_caracteristicas
        FOREIGN KEY (caracteristicas)
        REFERENCES caracteristicas_individuales(caracteristicas),
    CONSTRAINT fk_estilo_vida
        FOREIGN KEY (estiloVida)
        REFERENCES estilo_vida(estiloVida)
);

