package de.example.shogunref.dao;

import org.springframework.stereotype.Repository;

import de.example.shogunref.model.ProjectApplication;
import de.terrestris.shoguncore.dao.ApplicationDao;
import de.terrestris.shoguncore.model.Application;

/**
 * This is a demo DAO that demonstrates how a SHOGun-Core DAO can be extended.
 *
 * @author Nils Bühner
 *
 * @param <E>
 */
@Repository("projectApplicationDao")
public class ProjectApplicationDao<E extends Application> extends ApplicationDao<E> {

	/**
	 * Public default constructor for this DAO.
	 */
	@SuppressWarnings("unchecked")
	public ProjectApplicationDao() {
		super((Class<E>) ProjectApplication.class);
	}

	/**
	 * Constructor that has to be called by subclasses.
	 *
	 * @param clazz
	 */
	protected ProjectApplicationDao(Class<E> clazz) {
		super(clazz);
	}

}
